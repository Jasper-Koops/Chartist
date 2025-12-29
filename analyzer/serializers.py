from analyzer.models import PCAAnalysis, PCAComponentPartyScore
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
