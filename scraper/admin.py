from django.contrib import admin
from scraper.models import (
    ImportRun,
    Party,
    PartyAlias,
    ParliamentaryItem,
    PartySuccession,
    PartyVote,
)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["abbreviation", "name", "participation_rate"]
    search_fields = ["abbreviation", "name", "api_id"]
    readonly_fields = ["api_id", "participation_rate", "logo_length"]


@admin.register(ParliamentaryItem)
class ParliamentaryItemAdmin(admin.ModelAdmin):
    list_display = ["title", "item_type", "status", "date"]
    list_filter = ["item_type", "status"]
    search_fields = ["title", "api_id"]
    readonly_fields = ["api_id", "date"]


@admin.register(PartyVote)
class PartyVoteAdmin(admin.ModelAdmin):
    list_display = ["party", "parliamentary_item", "vote"]
    list_filter = ["vote", "party"]
    search_fields = [
        "party__name",
        "party__abbreviation",
        "parliamentary_item__title",
    ]
    raw_id_fields = ["party", "parliamentary_item"]


@admin.register(PartySuccession)
class PartySuccessionAdmin(admin.ModelAdmin):
    list_display = ["predecessor", "successor", "date", "member_overlap"]


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = [
        "started_at",
        "finished_at",
        "status",
        "created",
        "votes_created",
        "votes_updated",
        "votes_deleted",
    ]
    list_filter = ["status"]
    readonly_fields = [field.name for field in ImportRun._meta.fields]


@admin.register(PartyAlias)
class PartyAliasAdmin(admin.ModelAdmin):
    list_display = ["api_id", "party"]
    search_fields = ["api_id", "party__abbreviation", "party__name"]
