from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, OutputWrapper
from scraper.utils import ParliamentApi


class ProgressPrinter:
    """
    Prints import progress without flooding the output.

    In a terminal, a single line per stage is updated in place. Otherwise
    (e.g. when piped to a log file), a line is printed per 10% of progress.
    """

    def __init__(self, stdout: OutputWrapper) -> None:
        self.stdout = stdout
        self.is_tty: bool = stdout.isatty()
        self.stage: str | None = None
        self.last_step: int = -1

    def __call__(self, stage: str, done: int, total: int) -> None:
        if stage != self.stage:
            self.stage = stage
            self.last_step = -1

        percentage = done * 100 // total if total else 100
        line = f"{stage}: {done}/{total} ({percentage}%)"
        if self.is_tty:
            self.stdout.write(f"\r{line}", ending="")
            if done >= total:
                self.stdout.write("")
            self.stdout.flush()
        elif percentage // 10 > self.last_step:
            self.last_step = percentage // 10
            self.stdout.write(line)


class Command(BaseCommand):
    """
    Management command to import parties, items and votes from the Parliament
    API.
    """

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--refetch-texts",
            action="store_true",
            help="Re-download the text of every motion, also those that "
            "already have text.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        api: ParliamentApi = ParliamentApi(
            progress=ProgressPrinter(self.stdout)
        )
        self.stdout.write(self.style.SUCCESS("Importing party data"))
        api.import_parties()
        self.stdout.write(self.style.SUCCESS("Importing vote data"))
        result = api.import_votes(refetch_texts=options["refetch_texts"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed import: {result.motions} motions, "
                f"{result.created} new, {result.texts_fetched} texts fetched, "
                f"{result.texts_failed} texts failed"
            )
        )
