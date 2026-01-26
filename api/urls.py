from rest_framework import routers
from api.views import (
    PartyViewSet,
    PartyVoteViewSet,
    ParliamentaryItemViewSet,
    KeyParliamentaryItemViewSet,
    PCAAnalysisViewSet,
    PCAComponentPartyScoreViewSet,
    PCAItemLoadingViewSet,
)
from django.urls import path, include


router = routers.DefaultRouter()
router.register("parties", PartyViewSet)
router.register("votes", PartyVoteViewSet)
router.register("items", ParliamentaryItemViewSet)
router.register(
    "key-items", KeyParliamentaryItemViewSet, basename="key-parliamentary-items"
)
router.register("analysis", PCAAnalysisViewSet)
router.register("pca-scores", PCAComponentPartyScoreViewSet)
router.register("pca-loadings", PCAItemLoadingViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
