from django.urls import path

from analyzer.views import (
    ComponentDetailView,
    MotionDetailView,
    MotionListView,
    PairDetailView,
    PartyDetailView,
    TestGraph2View,
    TestGraphView,
)

urlpatterns = [
    path("test-graph/", TestGraphView.as_view(), name="test-graph"),
    path("test-graph-2/", TestGraph2View.as_view(), name="test-graph-2"),
    path("party/<int:pk>/", PartyDetailView.as_view(), name="party-detail"),
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
