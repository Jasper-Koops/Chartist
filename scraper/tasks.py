from celery import chain, shared_task
from scraper.utils import ParliamentApi, run_import
from analyzer.analysis import run_full_analysis


@shared_task
def import_votes() -> None:
    """Import parties, votes and motion texts."""
    run_import(ParliamentApi())


@shared_task
def run_scheduled_pca_analysis() -> None:
    """Run the full analysis after a successful import."""
    run_full_analysis(n_components=3)


@shared_task
def import_and_analyze() -> None:
    """
    Import votes, then run the analysis once the import has succeeded.

    The analysis starts after every successful import. If the import fails,
    the analysis does not run.
    """
    chain(import_votes.si(), run_scheduled_pca_analysis.si()).delay()
