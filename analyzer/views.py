from typing import Any

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView

from scraper.models import ParliamentaryItem, Party, PartySuccession


class TestGraphView(TemplateView):
    template_name = "test_graph.html"


class TestGraph2View(TemplateView):
    """Copy of the test page, as a sandbox for a UI redesign."""

    template_name = "test_graph2.html"


class PartyDetailView(TemplateView):
    """Test page for a single party; its charts load from the API."""

    template_name = "party_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        party = get_object_or_404(Party, pk=kwargs["pk"])
        context["party"] = party
        # A rename such as GroenLinks-PvdA -> PRO, in either direction.
        context["continues"] = (
            PartySuccession.objects.filter(successor=party)
            .select_related("predecessor")
            .first()
        )
        context["continued_as"] = (
            PartySuccession.objects.filter(predecessor=party)
            .select_related("successor")
            .first()
        )
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


class PairDetailView(TemplateView):
    """Test page comparing two parties; data loads from the API."""

    template_name = "pair_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs["pk"] == kwargs["other_pk"]:
            raise Http404("Choose two different parties.")
        context = super().get_context_data(**kwargs)
        context["party"] = get_object_or_404(Party, pk=kwargs["pk"])
        context["other_party"] = get_object_or_404(Party, pk=kwargs["other_pk"])
        return context


class ComponentDetailView(TemplateView):
    """
    Test page for one principal component of the newest analysis: which
    motions and parties drive it. Data loads from the API.
    """

    template_name = "component_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["number"] = kwargs["number"]
        return context
