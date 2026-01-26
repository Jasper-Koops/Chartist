from django.db.models.functions import Abs
from rest_framework.viewsets import ReadOnlyModelViewSet
from scraper.serializers import (
    PartySerializer,
    PartyVoteSerializer,
    ParliamentaryItemSerializer,
    KeyParliamentaryItemSerializer,
)
from api.errors import NoAnalysisFoundException
from django.db.models import Sum, QuerySet
from analyzer.serializers import (
    PCAAnalysisSerializer,
    PCAComponentPartyScoreSerializer,
    PCAItemLoadingSerializer,
)
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading
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


# FIXME - test
class KeyParliamentaryItemViewSet(ReadOnlyModelViewSet[ParliamentaryItem]):
    serializer_class = KeyParliamentaryItemSerializer
    filterset_fields = {
        "id": ["exact"],
    }

    def get_queryset(self) -> QuerySet[ParliamentaryItem]:
        latest_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        if not latest_analysis:
            raise NoAnalysisFoundException

        queryset = (
            ParliamentaryItem.objects.filter(
                pca_loadings__analysis=latest_analysis
            )
            .annotate(total_loading=Sum(Abs("pca_loadings__loading")))
            .order_by("-total_loading")[:10]
        )
        return queryset


class PCAAnalysisViewSet(ReadOnlyModelViewSet[PCAAnalysis]):
    queryset = PCAAnalysis.objects.all()
    serializer_class = PCAAnalysisSerializer
    filterset_fields = {
        "created_at": ["exact", "gte", "lte"],
    }


class PCAComponentPartyScoreViewSet(
    ReadOnlyModelViewSet[PCAComponentPartyScore]
):
    queryset = PCAComponentPartyScore.objects.all()
    serializer_class = PCAComponentPartyScoreSerializer
    filterset_fields = {
        "analysis": ["exact"],
        "party": ["exact"],
        "component": ["exact"],
        "score": ["exact", "gte", "lte"],
    }


class PCAItemLoadingViewSet(ReadOnlyModelViewSet[PCAItemLoading]):
    queryset = PCAItemLoading.objects.all()
    serializer_class = PCAItemLoadingSerializer
    filterset_fields = {
        "analysis": ["exact"],
        "parliamentary_item": ["exact"],
        "component": ["exact"],
        "loading": ["exact", "gte", "lte"],
    }
