from django.contrib import admin
from scraper.models import Party, ParliamentaryItem, PartyVote


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["abbreviation", "name", "participation_rate"]
    search_fields = ["abbreviation", "name", "api_id"]
    readonly_fields = ["api_id", "participation_rate"]


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
