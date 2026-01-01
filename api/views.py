from rest_framework.viewsets import ReadOnlyModelViewSet
from scraper.serializers import (
    PartySerializer,
    PartyVoteSerializer,
    ParliamentaryItemSerializer,
)
from analyzer.serializers import (
    PCAAnalysisSerializer,
    PCAComponentPartyScoreSerializer,
)
from analyzer.models import PCAAnalysis, PCAComponentPartyScore
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
