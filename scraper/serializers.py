from bisect import bisect_left

from rest_framework import serializers
from typing import Any
from analyzer.models import PCAAnalysis, PCAItemLoading
from scraper.models import Party, PartyVote, ParliamentaryItem


class PartySerializer(serializers.ModelSerializer[Party]):
    party_scores = serializers.SerializerMethodField()

    class Meta:
        model = Party
        fields = [
            "id",
            "api_id",
            "name",
            "abbreviation",
            "participation_rate",
            "logo_url",
            "party_scores",
        ]

    def get_party_scores(self, obj: Party) -> Any:
        # Avoid circular import.
        from analyzer.serializers import PartyPCAScoreSerializer

        # Scores of the newest analysis. PartyViewSet prefetches them for all
        # parties at once; otherwise they are queried here.
        scores = getattr(obj, "latest_scores", None)
        if scores is None:
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


class AxisRanks:
    """
    The newest analysis, with every motion's weight per axis sorted by
    strength (one query for all), to say how a motion's weight compares
    with those of all motions.
    """

    def __init__(self) -> None:
        self.analysis = PCAAnalysis.objects.order_by("-created_at").first()
        self.strengths: dict[int, list[float]] = {}
        if self.analysis is None:
            return
        for component_id, loading in PCAItemLoading.objects.filter(
            component__analysis=self.analysis
        ).values_list("component_id", "loading"):
            self.strengths.setdefault(component_id, []).append(abs(loading))
        for values in self.strengths.values():
            values.sort()

    def stronger_than(self, component_id: int, loading: float) -> float | None:
        """The share of motions whose weight on the axis is weaker."""
        values = self.strengths.get(component_id)
        if not values:
            return None
        return bisect_left(values, abs(loading)) / len(values)


class ParliamentaryItemListSerializer(ParliamentaryItemSerializer):
    """
    A list row with the motion's weight on each axis of the newest analysis
    and how it compares (`?axes=1`). Expects `newest_loadings` prefetched
    and `axis_ranks` (AxisRanks) in the context.
    """

    axes = serializers.SerializerMethodField()

    class Meta(ParliamentaryItemSerializer.Meta):
        fields = ParliamentaryItemSerializer.Meta.fields + ["axes"]

    def get_axes(self, obj: ParliamentaryItem) -> Any:
        ranks: AxisRanks = self.context["axis_ranks"]
        return [
            {
                "number": item.component.number,
                "loading": item.loading,
                "stronger_than": ranks.stronger_than(
                    item.component_id, item.loading
                ),
            }
            for item in sorted(
                getattr(obj, "newest_loadings", []),
                key=lambda item: item.component.number,
            )
        ]


class ParliamentaryItemDetailSerializer(ParliamentaryItemSerializer):
    """
    Adds the motion text, document links, the vote of every party and where
    the motion sits on the axes, which are left out of list responses.
    `text` is the full text as published; `core_text` only what the motion
    says, without the formula.
    """

    core_text = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    documents = serializers.SerializerMethodField()
    votes = serializers.SerializerMethodField()
    axes = serializers.SerializerMethodField()

    class Meta(ParliamentaryItemSerializer.Meta):
        fields = ParliamentaryItemSerializer.Meta.fields + [
            "text",
            "core_text",
            "document_id",
            "documents",
            "votes",
            "axes",
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
                "logo_url": vote.party.logo_url,
                "vote": vote.vote,
            }
            for vote in obj.partyvote_set.select_related("party").order_by(
                "party__abbreviation"
            )
        ]

    def get_axes(self, obj: ParliamentaryItem) -> Any:
        """
        Where the motion sits on each axis of the newest analysis: its
        loading (weight), the share of motions whose weight is weaker, and
        the three parties at each end of the axis (most extreme first).
        Parties at the high end tend to vote for motions with a positive
        weight and against those with a negative one. Empty without an
        analysis, or when the motion was not part of it.
        """
        ranks = AxisRanks()
        if ranks.analysis is None:
            return []
        rows = []
        for item in (
            obj.pca_loadings.filter(component__analysis=ranks.analysis)
            .select_related("component")
            .order_by("component__number")
        ):
            component = item.component
            parties = [
                score.party.abbreviation
                for score in component.party_scores.select_related(
                    "party"
                ).order_by("-score")
            ]
            rows.append(
                {
                    "component": component.id,
                    "number": component.number,
                    "explained_variance": component.explained_variance,
                    "loading": item.loading,
                    "stronger_than": ranks.stronger_than(
                        component.id, item.loading
                    ),
                    "high_end": parties[:3],
                    "low_end": parties[::-1][:3],
                }
            )
        return rows


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
