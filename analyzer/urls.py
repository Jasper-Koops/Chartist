from django.urls import path

from analyzer.views import TestGraphView

urlpatterns = [
    path("test-graph/", TestGraphView.as_view(), name="test-graph"),
]
