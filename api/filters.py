from django_filters import rest_framework as filters
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading


class PCAComponentPartyScoreFilter(filters.FilterSet):
    analysis = filters.ModelChoiceFilter(
        field_name="component__analysis",
        queryset=PCAAnalysis.objects.all(),
    )
    number = filters.NumberFilter(field_name="component__number")

    class Meta:
        model = PCAComponentPartyScore
        fields = {
            "component": ["exact"],
            "party": ["exact"],
            "score": ["exact", "gte", "lte"],
        }


class PCAItemLoadingFilter(filters.FilterSet):
    analysis = filters.ModelChoiceFilter(
        field_name="component__analysis",
        queryset=PCAAnalysis.objects.all(),
    )
    number = filters.NumberFilter(field_name="component__number")

    class Meta:
        model = PCAItemLoading
        fields = {
            "component": ["exact"],
            "parliamentary_item": ["exact"],
            "loading": ["exact", "gte", "lte"],
        }
