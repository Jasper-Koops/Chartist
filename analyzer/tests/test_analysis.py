from analyzer.analysis import run_pca_analysis, prepare_df
from django.test import TestCase
from django.db.models import QuerySet
from scraper.models import ParliamentaryItem, PartyVote
from analyzer.models import PCAAnalysis, PCAComponentPartyScore, PCAItemLoading
from analyzer.analysis import calculate_party_participation_rate
from analyzer.utils import AnalysisLogger
from scraper.tests.utils.testing_utils import (
    generate_party_votes,
    generate_parliamentary_items,
    generate_parties,
)
import logging

logger = logging.getLogger(__name__)


class TestCalculatePartyParticipationRate(TestCase):
    def setUp(self) -> None:
        self.parties = generate_parties()
        self.items = generate_parliamentary_items(5)

    def test_party_with_no_votes_has_zero_participation_rate(self) -> None:
        calculate_party_participation_rate()
        for party in self.parties:
            self.assertEqual(party.participation_rate, 0.0)

    def test_party_with_votes_has_correct_participation_rate(self) -> None:
        generate_party_votes(
            parliamentary_items=self.items,
            parties=self.parties,
            calculate_participation_rate=True,
        )
        for party in self.parties:
            total_votes: int = PartyVote.objects.filter(party=party).count()
            votes_cast: int = party.partyvote_set.count()
            expected_rate: float = (votes_cast / total_votes) * 100
            party.refresh_from_db()
            self.assertEqual(party.participation_rate, expected_rate)


class TestPrepareDF(TestCase):
    def setUp(self) -> None:
        self.log: AnalysisLogger = AnalysisLogger(logger, {})

    def test_prepare_df_returns_correct_shape(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(5),
            parties=generate_parties(),
            calculate_participation_rate=True,
        )
        prepared_df, labels = prepare_df(log=self.log)
        self.assertEqual(prepared_df.shape, (15, 5))
        items: QuerySet[ParliamentaryItem] = ParliamentaryItem.objects.filter(
            id__in=prepared_df.columns
        )
        self.assertEqual(5, items.count())

    def test_party_with_no_votes_is_handled(self) -> None:
        parties = generate_parties()
        last_party = parties.last()
        assert last_party
        parties_without_last = parties.exclude(id=last_party.id)
        items = generate_parliamentary_items(5)
        # Last party has no votes
        generate_party_votes(
            parliamentary_items=items,
            parties=parties_without_last,
            calculate_participation_rate=False,
        )
        calculate_party_participation_rate()
        prepared_df, labels = prepare_df(log=self.log)
        # One less party
        self.assertEqual(prepared_df.shape, (14, 5))


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
