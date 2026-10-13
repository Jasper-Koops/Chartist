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
from django.db.models import Sum, QuerySet
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
        "agreements__party"
    ).order_by("-created_at")
    serializer_class = AgreementMatrixSerializer
    filterset_fields = {
        "created_at": ["exact", "gte", "lte"],
    }
