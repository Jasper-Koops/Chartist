from django.urls import path

from analyzer.views import PartyDetailView, TestGraphView

urlpatterns = [
    path("test-graph/", TestGraphView.as_view(), name="test-graph"),
    path("party/<int:pk>/", PartyDetailView.as_view(), name="party-detail"),
]
