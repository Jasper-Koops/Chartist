from django.contrib import admin
from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)


@admin.register(PCAAnalysis)
class PCAAnalysisAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(PCAComponent)
class PCAComponentAdmin(admin.ModelAdmin):
    list_display = ["analysis", "number", "explained_variance"]
    list_filter = ["number"]
    raw_id_fields = ["analysis"]
    readonly_fields = ["number", "explained_variance"]


@admin.register(PCAComponentPartyScore)
class PCAComponentPartyScoreAdmin(admin.ModelAdmin):
    list_display = ["component", "party", "score"]
    list_filter = ["component__number", "party"]
    search_fields = ["party__name", "party__abbreviation"]
    raw_id_fields = ["component", "party"]
    readonly_fields = ["score"]


@admin.register(PCAItemLoading)
class PCAItemLoadingAdmin(admin.ModelAdmin):
    list_display = ["component", "parliamentary_item", "loading"]
    list_filter = ["component__number"]
    search_fields = [
        "parliamentary_item__title",
        "parliamentary_item__api_id",
    ]
    raw_id_fields = ["component", "parliamentary_item"]
    readonly_fields = ["loading"]
