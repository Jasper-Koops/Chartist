from rest_framework import serializers
from typing import Any
from analyzer.models import PCAAnalysis
from scraper.models import Party, PartyVote, ParliamentaryItem


class PartySerializer(serializers.ModelSerializer[Party]):
    party_scores = serializers.SerializerMethodField()

    class Meta:
        model = Party
        fields = ["id", "api_id", "name", "abbreviation", "party_scores"]

    def get_party_scores(self, obj: Party) -> Any:
        # Avoid circular import.
        from analyzer.serializers import PartyPCAScoreSerializer

        # Get last PCA analysis scores for this party
        last_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        if last_analysis is None:
            return []
        scores = obj.pca_scores.filter(
            component__analysis=last_analysis
        ).select_related("component")
        return PartyPCAScoreSerializer(scores, many=True).data


class PartyVoteSerializer(serializers.ModelSerializer[PartyVote]):
    class Meta:
        model = PartyVote
        fields = ["id", "party", "parliamentary_item", "vote"]


class ParliamentaryItemSerializer(
    serializers.ModelSerializer[ParliamentaryItem]
):
    class Meta:
        model = ParliamentaryItem
        fields = [
            "id",
            "api_id",
            "title",
            "date",
            "vote_date",
            "item_type",
            "status",
        ]


class ParliamentaryItemDetailSerializer(ParliamentaryItemSerializer):
    """
    Adds the motion text, document links and the vote of every party,
    which are left out of list responses.
    """

    documents = serializers.SerializerMethodField()
    votes = serializers.SerializerMethodField()

    class Meta(ParliamentaryItemSerializer.Meta):
        fields = ParliamentaryItemSerializer.Meta.fields + [
            "text",
            "document_id",
            "documents",
            "votes",
        ]

    def get_documents(self, obj: ParliamentaryItem) -> Any:
        # Official publication of the motion, as web page and PDF.
        if not obj.document_id:
            return []
        base = f"https://zoek.officielebekendmakingen.nl/{obj.document_id}"
        return [
            {"label": "Official publication", "url": f"{base}.html"},
            {"label": "PDF", "url": f"{base}.pdf"},
        ]

    def get_votes(self, obj: ParliamentaryItem) -> Any:
        # The votes as recorded, without votes inherited from a predecessor.
        return [
            {
                "party": vote.party_id,
                "abbreviation": vote.party.abbreviation,
                "name": vote.party.name,
                "vote": vote.vote,
            }
            for vote in obj.partyvote_set.select_related("party").order_by(
                "party__abbreviation"
            )
        ]


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
            "vote_date",
            "item_type",
            "status",
            "text",
            "votes",
            "loadings",
        ]

    def get_votes(self, obj: ParliamentaryItem) -> Any:
        votes = obj.partyvote_set.all()
        return PartyVoteSerializer(votes, many=True).data

    def get_loadings(self, obj: ParliamentaryItem) -> Any:
        # Avoid circular import.
        from analyzer.serializers import PCAItemLoadingSerializer

        last_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        if last_analysis is None:
            return []
        loadings = obj.pca_loadings.filter(component__analysis=last_analysis)
        return PCAItemLoadingSerializer(loadings, many=True).data
