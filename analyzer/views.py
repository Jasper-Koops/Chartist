from typing import Any
from datetime import datetime

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView, View

from scraper.models import ParliamentaryItem, Party, PartyLogo, PartySuccession
from scraper.utils import PERIOD_START
from analyzer.utils import (
    PARTICIPATION_THRESHOLD,
    PCA_FIT_COVERAGE,
    PCA_MIN_PROJECTED_VOTES,
)


class HomeView(TemplateView):
    """Landing page: the landscape, agreement matrix, parties and axes."""

    template_name = "home.html"


class MethodologyView(TemplateView):
    template_name = "methodology.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            period_start=datetime.fromisoformat(PERIOD_START).date(),
            participation_threshold=PARTICIPATION_THRESHOLD,
            fit_coverage=PCA_FIT_COVERAGE * 100,
            minimum_projected_votes=PCA_MIN_PROJECTED_VOTES,
        )
        return context


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


class PartyLogoView(View):
    """
    A party's logo, as stored by the import. Its URL carries a version
    (`Party.logo_url`), so the browser may keep it for a year.
    """

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        logo = get_object_or_404(PartyLogo, party_id=pk)
        response = HttpResponse(
            bytes(logo.image), content_type=logo.content_type
        )
        response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


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
