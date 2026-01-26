from rest_framework import serializers
from typing import Any
from analyzer.serializers import PCAItemLoadingSerializer
from scraper.models import Party, PartyVote, ParliamentaryItem
from analyzer.models import PCAItemLoading


class PartySerializer(serializers.ModelSerializer[Party]):
    class Meta:
        model = Party
        fields = ["id", "api_id", "name", "abbreviation"]


class PartyVoteSerializer(serializers.ModelSerializer[PartyVote]):
    class Meta:
        model = PartyVote
        fields = ["id", "party", "parliamentary_item", "vote"]


class ParliamentaryItemSerializer(
    serializers.ModelSerializer[ParliamentaryItem]
):
    class Meta:
        model = ParliamentaryItem
        fields = ["id", "api_id", "title", "date", "item_type", "status"]


class KeyParliamentaryItemSerializer(
    serializers.ModelSerializer[ParliamentaryItem]
):
    votes = serializers.SerializerMethodField()
    loadings = serializers.SerializerMethodField()

    class Meta:
        model = ParliamentaryItem
        fields = [
            "id",
            "api_id",
            "title",
            "date",
            "item_type",
            "status",
            "votes",
            "loadings",
        ]

    def get_votes(self, obj: ParliamentaryItem) -> Any:
        votes = PartyVote.objects.filter(parliamentary_item=obj)
        return PartyVoteSerializer(votes, many=True).data

    def get_loadings(self, obj: ParliamentaryItem) -> Any:
        loadings = PCAItemLoading.objects.filter(parliamentary_item=obj)
        return PCAItemLoadingSerializer(loadings, many=True).data
