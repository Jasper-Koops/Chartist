from analyzer.analysis import run_pca_analysis
from django.test import TestCase
from analyzer.models import PCAAnalysis, PCAComponentPartyScore

from scraper.tests.utils.testing_utils import (
    generate_party_votes,
    generate_parliamentary_items,
    generate_parties,
)


class TestRunPCAAnalysis(TestCase):
    def test_function_runs_without_error(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)
        self.assertEqual(1, PCAAnalysis.objects.count())
        self.assertEqual(45, PCAComponentPartyScore.objects.count())
