from analyzer.analysis import run_pca_analysis, prepare_df
from django.test import TestCase
from django.db.models import QuerySet
from scraper.models import ParliamentaryItem
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading

from scraper.tests.utils.testing_utils import (
    generate_party_votes,
    generate_parliamentary_items,
    generate_parties,
)


class TestPrepareDF(TestCase):
    def test_prepare_df_returns_correct_shape(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(5),
            parties=generate_parties(),
        )
        prepared_df, labels = prepare_df()
        self.assertEqual(prepared_df.shape, (15, 5))
        items: QuerySet[ParliamentaryItem] = ParliamentaryItem.objects.filter(
            id__in=prepared_df.columns
        )
        self.assertEqual(5, items.count())


class TestRunPCAAnalysis(TestCase):
    def test_function_runs_without_error(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)
        self.assertEqual(1, PCAAnalysis.objects.count())
        self.assertEqual(45, PCAComponentPartyScore.objects.count())
        self.assertEqual(10 * 3, PCAItemLoading.objects.count())
