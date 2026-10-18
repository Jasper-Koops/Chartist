from typing import Any

from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from scraper.models import ParliamentaryItem, Party


class TestGraphView(TemplateView):
    template_name = "test_graph.html"


class PartyDetailView(TemplateView):
    """Test page for a single party; its charts load from the API."""

    template_name = "party_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["party"] = get_object_or_404(Party, pk=kwargs["pk"])
        return context


class MotionListView(TemplateView):
    """Test page to search all motions; results load from the API."""

    template_name = "motion_list.html"


class MotionDetailView(TemplateView):
    """Test page for a single motion; text and votes load from the API."""

    template_name = "motion_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["motion"] = get_object_or_404(
            ParliamentaryItem, pk=kwargs["pk"]
        )
        return context
