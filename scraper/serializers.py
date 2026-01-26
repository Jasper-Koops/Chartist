from rest_framework import serializers
from typing import Any
from scraper.models import Party, PartyVote, ParliamentaryItem


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
        votes = obj.partyvote_set.all()
        return PartyVoteSerializer(votes, many=True).data

    def get_loadings(self, obj: ParliamentaryItem) -> Any:
        # Avoid circular import.
        from analyzer.serializers import PCAItemLoadingSerializer

        loadings = obj.pca_loadings.all()
        return PCAItemLoadingSerializer(loadings, many=True).data
