from analyzer.analysis import run_pca_analysis, prepare_df
from django.test import TestCase
from django.db.models import QuerySet
from scraper.models import ParliamentaryItem
from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
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
            party.refresh_from_db()
            self.assertEqual(party.participation_rate, 0.0)

    def test_party_with_votes_has_correct_participation_rate(self) -> None:
        generate_party_votes(
            parliamentary_items=self.items,
            parties=self.parties,
            calculate_participation_rate=True,
        )
        for party in self.parties:
            total_items: int = ParliamentaryItem.objects.count()
            votes_cast: int = party.partyvote_set.count()
            expected_rate: float = (votes_cast / total_items) * 100
            party.refresh_from_db()
            self.assertEqual(party.participation_rate, expected_rate)

    def test_partial_participation_rate(self) -> None:
        """Test that a party voting on only some items gets a rate < 100%."""
        subset = self.items[:3]
        party = self.parties.first()
        assert party is not None
        from scraper.tests.factories import PartyVoteFactory
        from scraper.models import VoteType

        for item in subset:
            PartyVoteFactory(
                party=party, parliamentary_item=item, vote=VoteType.FOR
            )
        calculate_party_participation_rate()
        party.refresh_from_db()
        expected_rate = (len(subset) / self.items.count()) * 100
        self.assertEqual(party.participation_rate, expected_rate)
        assert party.participation_rate is not None
        self.assertLess(party.participation_rate, 100.0)


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
    def setUp(self) -> None:
        self.parties = generate_parties()
        self.items = generate_parliamentary_items(10)
        generate_party_votes(
            parliamentary_items=self.items,
            parties=self.parties,
        )

    def test_creates_correct_record_counts(self) -> None:
        run_pca_analysis(n_components=3)
        self.assertEqual(1, PCAAnalysis.objects.count())
        self.assertEqual(3, PCAComponent.objects.count())
        self.assertEqual(45, PCAComponentPartyScore.objects.count())
        self.assertEqual(10 * 3, PCAItemLoading.objects.count())

    def test_components_have_valid_explained_variance(self) -> None:
        run_pca_analysis(n_components=3)
        components = list(
            PCAComponent.objects.order_by("number").values_list(
                "explained_variance", flat=True
            )
        )
        self.assertEqual(len(components), 3)
        # Each variance is between 0 and 1
        for variance in components:
            self.assertGreater(variance, 0)
            self.assertLessEqual(variance, 1)
        # Total explained variance cannot exceed 1
        self.assertLessEqual(sum(components), 1)
        # Components are in descending order of explained variance
        self.assertEqual(components, sorted(components, reverse=True))

    def test_scores_and_loadings_link_to_correct_components(self) -> None:
        run_pca_analysis(n_components=3)
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        for pca_component in PCAComponent.objects.filter(analysis=analysis):
            # Each component should have exactly 15 party scores (one per party)
            scores = PCAComponentPartyScore.objects.filter(
                component=pca_component
            )
            self.assertEqual(scores.count(), self.parties.count())
            # Each component should have exactly 10 item loadings (one per item)
            loadings = PCAItemLoading.objects.filter(component=pca_component)
            self.assertEqual(loadings.count(), self.items.count())

    def test_cascade_delete_removes_all_related_records(self) -> None:
        run_pca_analysis(n_components=3)
        self.assertEqual(1, PCAAnalysis.objects.count())
        PCAAnalysis.objects.all().delete()
        self.assertEqual(0, PCAComponent.objects.count())
        self.assertEqual(0, PCAComponentPartyScore.objects.count())
        self.assertEqual(0, PCAItemLoading.objects.count())
