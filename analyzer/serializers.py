from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading
from rest_framework import serializers


class PCAAnalysisSerializer(serializers.ModelSerializer[PCAAnalysis]):
    class Meta:
        model = PCAAnalysis
        fields: list[str] = ["id", "created_at"]


class PCAComponentPartyScoreSerializer(
    serializers.ModelSerializer[PCAComponentPartyScore]
):
    class Meta:
        model = PCAComponentPartyScore
        fields: list[str] = ["id", "analysis", "party", "component", "score"]


class PCAItemLoadingSerializer(serializers.ModelSerializer[PCAItemLoading]):
    class Meta:
        model = PCAItemLoading
        fields: list[str] = [
            "id",
            "analysis",
            "parliamentary_item",
            "component",
            "loading",
        ]
