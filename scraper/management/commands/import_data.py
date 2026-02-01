from django.core.management.base import BaseCommand
from scraper.utils import ParliamentApi


class Command(BaseCommand):
    """
    Management command to import parties, items and votes from the Parliament
    API.
    """

    def handle(self, *args: list[str], **options: dict[str, str]) -> None:
        api: ParliamentApi = ParliamentApi()
        self.stdout.write(self.style.SUCCESS("Importing party data"))
        api.import_parties()
        self.stdout.write(self.style.SUCCESS("Importing vote data"))
        api.import_votes()
        self.stdout.write(self.style.SUCCESS("Completed import"))
