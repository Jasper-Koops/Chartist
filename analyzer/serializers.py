from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
from rest_framework import serializers


class PCAComponentSerializer(serializers.ModelSerializer[PCAComponent]):
    class Meta:
        model = PCAComponent
        fields: list[str] = ["id", "analysis", "number", "explained_variance"]


class PCAAnalysisSerializer(serializers.ModelSerializer[PCAAnalysis]):
    components = PCAComponentSerializer(many=True, read_only=True)

    class Meta:
        model = PCAAnalysis
        fields: list[str] = ["id", "created_at", "components"]


class PCAComponentPartyScoreSerializer(
    serializers.ModelSerializer[PCAComponentPartyScore]
):
    class Meta:
        model = PCAComponentPartyScore
        fields: list[str] = ["id", "component", "party", "score"]


class PCAItemLoadingSerializer(serializers.ModelSerializer[PCAItemLoading]):
    class Meta:
        model = PCAItemLoading
        fields: list[str] = [
            "id",
            "component",
            "parliamentary_item",
            "loading",
        ]
