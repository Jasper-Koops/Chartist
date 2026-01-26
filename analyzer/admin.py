from django.contrib import admin
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading


@admin.register(PCAAnalysis)
class PCAAnalysisAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(PCAComponentPartyScore)
class PCAComponentPartyScoreAdmin(admin.ModelAdmin):
    list_display = ["analysis", "party", "component", "score"]
    list_filter = ["component", "party"]
    search_fields = ["party__name", "party__abbreviation", "analysis__id"]
    raw_id_fields = ["analysis", "party"]
    readonly_fields = ["score", "component"]


@admin.register(PCAItemLoading)
class PCAItemLoadingAdmin(admin.ModelAdmin):
    list_display = ["analysis", "parliamentary_item", "component", "loading"]
    list_filter = ["component"]
    search_fields = [
        "parliamentary_item__title",
        "parliamentary_item__api_id",
    ]
    raw_id_fields = ["analysis", "parliamentary_item"]
    readonly_fields = ["loading", "component"]
