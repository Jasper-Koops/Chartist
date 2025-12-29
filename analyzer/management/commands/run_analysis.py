from django.core.management.base import BaseCommand
from analyzer.analysis import run_pca_analysis


class Command(BaseCommand):
    def handle(self, *args: list[str], **options: dict[str, str]) -> None:
        run_pca_analysis(n_components=3)
        self.stdout.write(self.style.SUCCESS("Analysis completed"))
