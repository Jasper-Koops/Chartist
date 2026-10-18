import json

from django.db.models import Q, QuerySet, TextField
from django.db.models.functions import Cast
from django_filters import rest_framework as filters
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading
from scraper.models import ParliamentaryItem


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


class ParliamentaryItemFilter(filters.FilterSet):
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = ParliamentaryItem
        fields = {
            "id": ["exact"],
            "title": ["exact", "icontains"],
            "date": ["exact", "gte", "lte"],
            "vote_date": ["exact", "gte", "lte"],
            "item_type": ["exact"],
            "status": ["exact"],
        }

    def filter_search(
        self, queryset: QuerySet[ParliamentaryItem], name: str, value: str
    ) -> QuerySet[ParliamentaryItem]:
        """
        Case-insensitive search in the title and the motion text.

        The text is stored as JSON, which escapes non-ASCII characters
        ('coördinatie' as 'co\\u00f6rdinatie'), so the escaped form of the
        search term is matched too.
        """
        value = value.strip()
        if not value:
            return queryset
        escaped = json.dumps(value)[1:-1]
        return queryset.annotate(text_json=Cast("text", TextField())).filter(
            Q(title__icontains=value)
            | Q(text_json__icontains=value)
            | Q(text_json__icontains=escaped)
        )
