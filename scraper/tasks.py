import logging

from celery import chain, shared_task
from scraper.utils import ParliamentApi, run_import
from analyzer.analysis import run_full_analysis

logger = logging.getLogger(__name__)


@shared_task
def import_votes() -> bool:
    """
    Import parties and votes.

    Returns:
        bool: Whether any votes changed, i.e. whether the analysis input
            changed.
    """
    result = run_import(ParliamentApi())
    return result.has_vote_changes


@shared_task
def run_scheduled_pca_analysis(votes_changed: bool = True) -> None:
    """
    Run the analysis, unless the preceding import changed no votes.

    Args:
        votes_changed (bool): Result of the preceding `import_votes` task in
            a chain. Defaults to True so the task can also run on its own.
    """
    if not votes_changed:
        logger.info("No vote changes since the last import, skipping analysis")
        return
    run_full_analysis(n_components=3)


@shared_task
def import_and_analyze() -> None:
    """
    Import votes, then run the analysis once the import has succeeded.

    The analysis only starts after the import finishes, and is skipped when
    the import changed no votes. If the import fails, the analysis does not
    run.
    """
    chain(import_votes.si(), run_scheduled_pca_analysis.s()).delay()
