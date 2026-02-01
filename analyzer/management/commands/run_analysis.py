from django.core.management.base import BaseCommand
from analyzer.analysis import run_full_analysis


class Command(BaseCommand):
    def handle(self, *args: list[str], **options: dict[str, str]) -> None:
        run_full_analysis(n_components=3, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Analysis completed"))
