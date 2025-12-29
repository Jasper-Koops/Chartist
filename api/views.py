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


class PartyVoteViewSet(ReadOnlyModelViewSet[PartyVote]):
    queryset = PartyVote.objects.all()
    serializer_class = PartyVoteSerializer


class ParliamentaryItemViewSet(ReadOnlyModelViewSet[ParliamentaryItem]):
    queryset = ParliamentaryItem.objects.all()
    serializer_class = ParliamentaryItemSerializer


class PCAAnalysisViewSet(ReadOnlyModelViewSet[PCAAnalysis]):
    queryset = PCAAnalysis.objects.all()
    serializer_class = PCAAnalysisSerializer


class PCAComponentPartyScoreViewSet(
    ReadOnlyModelViewSet[PCAComponentPartyScore]
):
    queryset = PCAComponentPartyScore.objects.all()
    serializer_class = PCAComponentPartyScoreSerializer
