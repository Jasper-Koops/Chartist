from django.urls import path

from analyzer.views import (
    ComponentDetailView,
    HomeView,
    MethodologyView,
    MotionDetailView,
    MotionListView,
    PairDetailView,
    PartyDetailView,
    PartyLogoView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("methodology/", MethodologyView.as_view(), name="methodology"),
    path("party/<int:pk>/", PartyDetailView.as_view(), name="party-detail"),
    path("party/<int:pk>/logo/", PartyLogoView.as_view(), name="party-logo"),
    path(
        "pair/<int:pk>/<int:other_pk>/",
        PairDetailView.as_view(),
        name="pair-detail",
    ),
    path(
        "component/<int:number>/",
        ComponentDetailView.as_view(),
        name="component-detail",
    ),
    path("motions/", MotionListView.as_view(), name="motion-list"),
    path("motion/<int:pk>/", MotionDetailView.as_view(), name="motion-detail"),
]
