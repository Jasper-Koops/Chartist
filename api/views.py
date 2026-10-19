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
from analyzer.compare import RELATIONS, pair_votes, related_items, summarize
from api.errors import NoAnalysisFoundException
from django.db.models import (
    Count,
    Exists,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    QuerySet,
    Sum,
)
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
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
from api.filters import (
    ParliamentaryItemFilter,
    PCAComponentPartyScoreFilter,
    PCAItemLoadingFilter,
)
from scraper.models import (
    ImportRun,
    ImportRunStatus,
    Party,
    PartyVote,
    ParliamentaryItem,
)


class PartyViewSet(ReadOnlyModelViewSet[Party]):
    queryset = Party.objects.all()
    serializer_class = PartySerializer
    filterset_fields = ["id", "abbreviation", "name"]

    def get_queryset(self) -> QuerySet[Party]:
        # Prefetch the newest analysis' scores for all parties in one query,
        # instead of two queries per party in the serializer.
        latest = PCAAnalysis.objects.order_by("-created_at").first()
        scores = PCAComponentPartyScore.objects.filter(
            component__analysis=latest
        ).select_related("component")
        return Party.objects.prefetch_related(
            Prefetch("pca_scores", queryset=scores, to_attr="latest_scores")
        )

    def _other_party(self, other_pk: str) -> Party:
        try:
            return Party.objects.get(pk=int(other_pk))
        except (Party.DoesNotExist, ValueError):
            raise NotFound("Party to compare with not found.")

    @action(detail=True, url_path=r"compare/(?P<other_pk>\d+)")
    def compare(
        self, request: Request, pk: str | None = None, other_pk: str = ""
    ) -> Response:
        """
        How this party voted relative to another: shared motions, agreement,
        opposite votes in each direction, and the monthly agreement of the
        pair from the newest agreement matrix.
        """
        party = self.get_object()
        other = self._other_party(other_pk)
        summary = summarize(pair_votes(party.id, other.id))

        matrix = AgreementMatrix.objects.order_by("-created_at").first()
        timeline = (
            [
                {
                    "month": row.month,
                    "agreement": row.agreement,
                    "shared_motions": row.shared_motions,
                }
                for row in PartyAgreement.objects.filter(
                    matrix=matrix,
                    party=party,
                    other_party=other,
                    month__isnull=False,
                ).order_by("month")
            ]
            if matrix
            else []
        )
        return Response(
            {
                "party": {
                    "id": party.id,
                    "abbreviation": party.abbreviation,
                    "name": party.name,
                },
                "other_party": {
                    "id": other.id,
                    "abbreviation": other.abbreviation,
                    "name": other.name,
                },
                "shared_motions": summary.shared_motions,
                "agreed": summary.agreed,
                "agreement": summary.agreement,
                "party_for_other_against": summary.party_for_other_against,
                "party_against_other_for": summary.party_against_other_for,
                "same_lineage": summary.same_lineage,
                "timeline": timeline,
            }
        )

    @action(detail=True, url_path=r"compare/(?P<other_pk>\d+)/motions")
    def compare_motions(
        self, request: Request, pk: str | None = None, other_pk: str = ""
    ) -> Response:
        """
        Motions with the votes of both parties, newest vote first.

        Query parameters: `relation` ("differed" (default), "agreed" or
        "all"), plus the motion filters, e.g. `search`, and pagination.
        A vote inherited from a predecessor names that predecessor (its `id`
        and `abbreviation`) in `party_vote_inherited_from` /
        `other_party_vote_inherited_from`.
        """
        party = self.get_object()
        other = self._other_party(other_pk)
        relation = request.query_params.get("relation", "differed")
        if relation not in RELATIONS:
            raise ValidationError(
                {"relation": f"Use one of: {', '.join(RELATIONS)}."}
            )
        pair = pair_votes(party.id, other.id)
        queryset = ParliamentaryItemFilter(
            data=request.query_params,
            queryset=ParliamentaryItem.objects.filter(
                id__in=related_items(pair.votes, pair.other_votes, relation)
            ).order_by(F("vote_date").desc(nulls_last=True), "-id"),
        ).qs
        page = self.paginate_queryset(queryset)
        items = page if page is not None else list(queryset)
        # The predecessors that cast inherited votes on this page, e.g.
        # GroenLinks-PvdA for PRO.
        source_ids = {
            sources[item.id]
            for item in items
            for sources in (pair.sources, pair.other_sources)
            if item.id in sources
        }
        predecessors = {
            party_id: {"id": party_id, "abbreviation": abbreviation}
            for party_id, abbreviation in Party.objects.filter(
                id__in=source_ids
            ).values_list("id", "abbreviation")
        }

        def inherited_from(sources: dict[int, int], item_id: int) -> Any:
            source = sources.get(item_id)
            return predecessors[source] if source is not None else None

        data = [
            {
                **ParliamentaryItemSerializer(item).data,
                "party_vote": pair.votes.get(item.id),
                "party_vote_inherited_from": inherited_from(
                    pair.sources, item.id
                ),
                "other_party_vote": pair.other_votes.get(item.id),
                "other_party_vote_inherited_from": inherited_from(
                    pair.other_sources, item.id
                ),
            }
            for item in items
        ]
        if page is None:
            return Response(data)
        return self.get_paginated_response(data)

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
    # Newest vote first by default; ?ordering= overrides it.
    queryset = ParliamentaryItem.objects.order_by(
        F("vote_date").desc(nulls_last=True), "-id"
    )
    serializer_class = ParliamentaryItemSerializer
    filterset_class = ParliamentaryItemFilter

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

    @action(detail=True)
    def breakdown(self, request: Request, pk: str | None = None) -> Response:
        """
        What a component consists of: the party scores along it, and the
        motions with the strongest positive and negative loadings, and how
        many motions share each side's strongest loading.

        Parties with a high score tend to vote for the motions with a
        positive loading and against those with a negative loading.
        Query parameter `limit` (default 25, max 200) sets the number of
        motions per side.
        """
        component = self.get_object()
        try:
            limit = min(max(int(request.query_params.get("limit", 25)), 1), 200)
        except ValueError:
            raise ValidationError({"limit": "Must be a number."})

        loadings = PCAItemLoading.objects.filter(
            component=component
        ).select_related("parliamentary_item")

        def motions(order: str) -> list[dict[str, Any]]:
            # Motions with the same voting pattern share a loading; among
            # equal loadings the newest vote comes first.
            rows = loadings.order_by(
                order,
                F("parliamentary_item__vote_date").desc(nulls_last=True),
                "-parliamentary_item_id",
            )[:limit]
            return [
                {
                    **ParliamentaryItemSerializer(row.parliamentary_item).data,
                    "loading": row.loading,
                }
                for row in rows
            ]

        def tied(extreme: float | None) -> int:
            # Motions sharing the strongest loading of a side.
            if extreme is None:
                return 0
            return loadings.filter(
                loading__gte=extreme - 1e-9, loading__lte=extreme + 1e-9
            ).count()

        positive = motions("-loading")
        negative = motions("loading")

        return Response(
            {
                "id": component.id,
                "number": component.number,
                "explained_variance": component.explained_variance,
                "analysis": component.analysis_id,
                "created_at": component.analysis.created_at,
                "parties": [
                    {
                        "id": score.party_id,
                        "abbreviation": score.party.abbreviation,
                        "score": score.score,
                    }
                    for score in component.party_scores.select_related(
                        "party"
                    ).order_by("-score")
                ],
                "positive": positive,
                "negative": negative,
                "tied_at_strongest_positive": tied(
                    positive[0]["loading"] if positive else None
                ),
                "tied_at_strongest_negative": tied(
                    negative[0]["loading"] if negative else None
                ),
            }
        )


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
    How fresh the data is: when the last successful sync with the API
    finished (and when the last one failed, if it did), the oldest and newest
    voting date, the number of motions with votes, and when the newest
    analysis and agreement matrix were made.
    """

    def get(self, request: Request) -> Response:
        # One query: an existence check per motion instead of a join with
        # every vote.
        voted = ParliamentaryItem.objects.filter(
            Exists(PartyVote.objects.filter(parliamentary_item=OuterRef("pk")))
        ).aggregate(
            count=Count("id"),
            earliest=Min("vote_date"),
            latest=Max("vote_date"),
        )
        latest_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        latest_matrix = AgreementMatrix.objects.order_by("-created_at").first()
        last_success = ImportRun.objects.filter(
            status=ImportRunStatus.SUCCEEDED
        ).first()
        latest_run = ImportRun.objects.first()
        return Response(
            {
                "last_synced_at": (
                    last_success.finished_at if last_success else None
                ),
                # Only set when the most recent sync failed.
                "last_sync_failed_at": (
                    latest_run.finished_at
                    if latest_run
                    and latest_run.status == ImportRunStatus.FAILED
                    else None
                ),
                "earliest_vote_date": voted["earliest"],
                "latest_vote_date": voted["latest"],
                "motions_with_votes": voted["count"],
                "latest_analysis_at": (
                    latest_analysis.created_at if latest_analysis else None
                ),
                "latest_agreement_matrix_at": (
                    latest_matrix.created_at if latest_matrix else None
                ),
            }
        )
