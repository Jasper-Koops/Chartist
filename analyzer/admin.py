from django.contrib import admin
from analyzer.models import PCAAnalysis, PCAComponentPartyScore


@admin.register(PCAAnalysis)
class PCAAnalysisAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(PCAComponentPartyScore)
class PCAComponentPartyScoreAdmin(admin.ModelAdmin):
    list_display = ["analysis", "party", "component", "score"]
    list_filter = ["component", "analysis", "party"]
    search_fields = ["party__name", "party__abbreviation", "analysis__id"]
    raw_id_fields = ["analysis", "party"]
    readonly_fields = ["score", "component"]
