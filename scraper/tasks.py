from celery import shared_task
from scraper.utils import ParliamentApi
from analyzer.analysis import run_pca_analysis


@shared_task
def import_votes() -> None:
    api = ParliamentApi()
    api.import_parties()
    api.import_votes()


@shared_task
def run_scheduled_pca_analysis() -> None:
    run_pca_analysis(n_components=3)
