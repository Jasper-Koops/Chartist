from rest_framework import serializers
from scraper.models import Party, PartyVote, ParliamentaryItem


class PartySerializer(serializers.ModelSerializer[Party]):
    class Meta:
        model = Party
        fields = ["api_id", "name", "abbreviation"]


class PartyVoteSerializer(serializers.ModelSerializer[PartyVote]):
    class Meta:
        model = PartyVote
        fields = ["party", "parliamentary_item", "vote"]


class ParliamentaryItemSerializer(
    serializers.ModelSerializer[ParliamentaryItem]
):
    class Meta:
        model = ParliamentaryItem
        fields = ["api_id", "title", "date", "item_type", "status"]
