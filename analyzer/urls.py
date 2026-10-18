from django.urls import path

from analyzer.views import (
    MotionDetailView,
    MotionListView,
    PartyDetailView,
    TestGraphView,
)

urlpatterns = [
    path("test-graph/", TestGraphView.as_view(), name="test-graph"),
    path("party/<int:pk>/", PartyDetailView.as_view(), name="party-detail"),
    path("motions/", MotionListView.as_view(), name="motion-list"),
    path("motion/<int:pk>/", MotionDetailView.as_view(), name="motion-detail"),
]
