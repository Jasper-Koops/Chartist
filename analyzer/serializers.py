from typing import Any
from analyzer.models import (
    AgreementMatrix,
    PartyAgreement,
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
        fields: list[str] = [
            "id",
            "created_at",
            "total_explained_variance",
            "components",
        ]


class PCAComponentPartyScoreSerializer(
    serializers.ModelSerializer[PCAComponentPartyScore]
):
    class Meta:
        model = PCAComponentPartyScore
        fields: list[str] = ["id", "component", "party", "score"]


class PartyPCAScoreSerializer(
    serializers.ModelSerializer[PCAComponentPartyScore]
):
    """
    Score nested under a party, keyed by the component's PC number.
    """

    component = serializers.IntegerField(
        source="component.number", read_only=True
    )

    class Meta:
        model = PCAComponentPartyScore
        fields: list[str] = ["component", "score"]


class PCAItemLoadingSerializer(serializers.ModelSerializer[PCAItemLoading]):
    class Meta:
        model = PCAItemLoading
        fields: list[str] = [
            "id",
            "component",
            "parliamentary_item",
            "loading",
        ]


class PartyAgreementSerializer(serializers.ModelSerializer[PartyAgreement]):
    class Meta:
        model = PartyAgreement
        fields: list[str] = [
            "party",
            "other_party",
            "agreement",
            "shared_motions",
        ]


class AgreementPartySerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    abbreviation = serializers.CharField()


class AgreementMatrixSerializer(serializers.ModelSerializer[AgreementMatrix]):
    """
    A matrix with its parties and all ordered pairs over the whole period.
    Parties are listed so a client can build the grid without fetching
    /parties/. Monthly rows are served by the party timeline endpoint.
    """

    parties = serializers.SerializerMethodField()
    agreements = serializers.SerializerMethodField()

    class Meta:
        model = AgreementMatrix
        fields: list[str] = ["id", "created_at", "parties", "agreements"]

    @staticmethod
    def overall(obj: AgreementMatrix) -> list[PartyAgreement]:
        # Prefetched by AgreementMatrixViewSet; queried otherwise.
        prefetched = getattr(obj, "overall_agreements", None)
        if prefetched is not None:
            return list(prefetched)
        return list(
            obj.agreements.filter(month__isnull=True).select_related("party")
        )

    def get_agreements(self, obj: AgreementMatrix) -> Any:
        return PartyAgreementSerializer(self.overall(obj), many=True).data

    def get_parties(self, obj: AgreementMatrix) -> Any:
        parties = {
            agreement.party_id: agreement.party.abbreviation
            for agreement in self.overall(obj)
        }
        return AgreementPartySerializer(
            [
                {"id": party_id, "abbreviation": abbreviation}
                for party_id, abbreviation in sorted(
                    parties.items(), key=lambda p: p[1]
                )
            ],
            many=True,
        ).data
