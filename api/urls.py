from rest_framework import routers
from api.views import (
    PartyViewSet,
    PartyVoteViewSet,
    ParliamentaryItemViewSet,
    PCAAnalysisViewSet,
    PCAComponentPartyScoreViewSet,
)
from django.urls import path, include


router = routers.DefaultRouter()
router.register("parties", PartyViewSet)
router.register("votes", PartyVoteViewSet)
router.register("items", ParliamentaryItemViewSet)
router.register("analysis", PCAAnalysisViewSet)
router.register("pca-scores", PCAComponentPartyScoreViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
