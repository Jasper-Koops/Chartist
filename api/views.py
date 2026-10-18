from typing import Any
from django.db.models.functions import Abs
from rest_framework.viewsets import ReadOnlyModelViewSet
from scraper.serializers import (
    PartySerializer,
    PartyVoteSerializer,
    ParliamentaryItemSerializer,
    ParliamentaryItemDetailSerializer,
    KeyParliamentaryItemSerializer,
)
from api.errors import NoAnalysisFoundException
from django.db.models import Max, Prefetch, Sum, QuerySet
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.serializers import BaseSerializer
from analyzer.serializers import (
    AgreementMatrixSerializer,
    PCAAnalysisSerializer,
    PCAComponentSerializer,
    PCAComponentPartyScoreSerializer,
    PCAItemLoadingSerializer,
)
from analyzer.models import (
    AgreementMatrix,
    PartyAgreement,
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
from api.filters import PCAComponentPartyScoreFilter, PCAItemLoadingFilter
from scraper.models import Party, PartyVote, ParliamentaryItem


class PartyViewSet(ReadOnlyModelViewSet[Party]):
    queryset = Party.objects.all()
    serializer_class = PartySerializer
    filterset_fields = ["id", "abbreviation", "name"]

    @action(detail=True, url_path="agreement-timeline")
    def agreement_timeline(
        self, request: Request, pk: str | None = None
    ) -> Response:
        """
        Monthly agreement of this party with every other party, from the
        newest agreement matrix. Months are calendar months by voting date;
        a month is only listed for a pair that shared motions in it.
        """
        party = self.get_object()
        matrix = AgreementMatrix.objects.order_by("-created_at").first()
        if matrix is None:
            raise NoAnalysisFoundException(
                "No agreement matrix has been calculated yet."
            )
        rows = (
            PartyAgreement.objects.filter(
                matrix=matrix, party=party, month__isnull=False
            )
            .select_related("other_party")
            .order_by("other_party__abbreviation", "month")
        )
        series: dict[int, dict[str, Any]] = {}
        for row in rows:
            entry = series.setdefault(
                row.other_party_id,
                {
                    "party": row.other_party_id,
                    "abbreviation": row.other_party.abbreviation,
                    "points": [],
                },
            )
            entry["points"].append(
                {
                    "month": row.month,
                    "agreement": row.agreement,
                    "shared_motions": row.shared_motions,
                }
            )
        months = sorted({row.month for row in rows if row.month is not None})
        return Response(
            {
                "matrix": matrix.id,
                "created_at": matrix.created_at,
                "party": party.id,
                "months": months,
                "series": list(series.values()),
            }
        )


class PartyVoteViewSet(ReadOnlyModelViewSet[PartyVote]):
    queryset = PartyVote.objects.all()
    serializer_class = PartyVoteSerializer
    filterset_fields = {
        "id": ["exact"],
        "party": ["exact"],
        "party__abbreviation": ["exact"],
        "parliamentary_item": ["exact"],
        "vote": ["exact"],
    }


class ParliamentaryItemViewSet(ReadOnlyModelViewSet[ParliamentaryItem]):
    queryset = ParliamentaryItem.objects.all()
    serializer_class = ParliamentaryItemSerializer
    filterset_fields = {
        "id": ["exact"],
        "title": ["exact", "icontains"],
        "date": ["exact", "gte", "lte"],
        "item_type": ["exact"],
        "status": ["exact"],
    }

    def get_serializer_class(self) -> type[BaseSerializer[ParliamentaryItem]]:
        # The motion text is only included on the detail route.
        if self.action == "retrieve":
            return ParliamentaryItemDetailSerializer
        return ParliamentaryItemSerializer


class KeyParliamentaryItemViewSet(ReadOnlyModelViewSet[ParliamentaryItem]):
    """
    The 10 items with the highest total absolute loading across all
    components of the latest analysis.
    """

    serializer_class = KeyParliamentaryItemSerializer
    filterset_fields = {
        "id": ["exact"],
    }

    def get_queryset(self) -> QuerySet[ParliamentaryItem]:
        latest_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        if not latest_analysis:
            raise NoAnalysisFoundException

        queryset = ParliamentaryItem.objects.filter(
            pca_loadings__component__analysis=latest_analysis
        ).annotate(total_loading=Sum(Abs("pca_loadings__loading")))

        # Select the top 10 ids first and return an unsliced queryset, so the
        # filter and ordering backends and the detail route can still apply.
        top_ids = list(
            queryset.order_by("-total_loading").values_list("id", flat=True)[
                :10
            ]
        )
        return queryset.filter(id__in=top_ids).order_by("-total_loading")


class PCAAnalysisViewSet(ReadOnlyModelViewSet[PCAAnalysis]):
    queryset = PCAAnalysis.objects.all()
    serializer_class = PCAAnalysisSerializer
    filterset_fields = {
        "created_at": ["exact", "gte", "lte"],
    }


class PCAComponentViewSet(ReadOnlyModelViewSet[PCAComponent]):
    queryset = PCAComponent.objects.all()
    serializer_class = PCAComponentSerializer
    filterset_fields = {
        "analysis": ["exact"],
        "number": ["exact"],
    }


class PCAComponentPartyScoreViewSet(
    ReadOnlyModelViewSet[PCAComponentPartyScore]
):
    queryset = PCAComponentPartyScore.objects.all()
    serializer_class = PCAComponentPartyScoreSerializer
    filterset_class = PCAComponentPartyScoreFilter


class PCAItemLoadingViewSet(ReadOnlyModelViewSet[PCAItemLoading]):
    queryset = PCAItemLoading.objects.all()
    serializer_class = PCAItemLoadingSerializer
    filterset_class = PCAItemLoadingFilter


class AgreementMatrixViewSet(ReadOnlyModelViewSet[AgreementMatrix]):
    """Stored agreement matrices, newest first."""

    queryset = AgreementMatrix.objects.prefetch_related(
        Prefetch(
            "agreements",
            queryset=PartyAgreement.objects.filter(
                month__isnull=True
            ).select_related("party"),
            to_attr="overall_agreements",
        )
    ).order_by("-created_at")
    serializer_class = AgreementMatrixSerializer
    filterset_fields = {
        "created_at": ["exact", "gte", "lte"],
    }


class StatusView(APIView):
    """
    How fresh the data is: the newest voting date, the number of motions
    with votes, and when the newest analysis and agreement matrix were made.
    """

    def get(self, request: Request) -> Response:
        voted = ParliamentaryItem.objects.filter(
            partyvote__isnull=False
        ).distinct()
        latest_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        latest_matrix = AgreementMatrix.objects.order_by("-created_at").first()
        return Response(
            {
                "latest_vote_date": voted.aggregate(latest=Max("vote_date"))[
                    "latest"
                ],
                "motions_with_votes": voted.count(),
                "latest_analysis_at": (
                    latest_analysis.created_at if latest_analysis else None
                ),
                "latest_agreement_matrix_at": (
                    latest_matrix.created_at if latest_matrix else None
                ),
            }
        )
