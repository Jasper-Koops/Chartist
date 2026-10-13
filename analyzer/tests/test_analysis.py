from datetime import datetime, timedelta, timezone
from io import StringIO

import numpy as np
import pandas as pd
from analyzer.analysis import (
    generate_pca_object,
    run_full_analysis,
    run_pca_analysis,
    prepare_df,
)
from django.db import IntegrityError
from django.test import TestCase
from django.db.models import QuerySet
from scraper.models import Party, ParliamentaryItem, VoteType
from scraper.tests.factories import (
    ParliamentaryItemFactory,
    PartyFactory,
    PartyVoteFactory,
)
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

    def test_party_voting_on_everything_has_100_percent(self) -> None:
        generate_party_votes(
            parliamentary_items=self.items,
            parties=self.parties,
            calculate_participation_rate=True,
        )
        for party in self.parties:
            party.refresh_from_db()
            self.assertEqual(100.0, party.participation_rate)


class TestParticipationFromPartyStart(TestCase):
    """Participation is measured from each party's own first vote."""

    def setUp(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.items = [
            self.item(start + timedelta(days=day)) for day in range(10)
        ]
        self.established = self.party()

    def item(self, date: datetime) -> ParliamentaryItem:
        item: ParliamentaryItem = ParliamentaryItemFactory(date=date)
        return item

    def party(self) -> Party:
        party: Party = PartyFactory()
        return party

    def vote(self, party: Party, items: list[ParliamentaryItem]) -> None:
        for item in items:
            PartyVoteFactory(
                party=party, parliamentary_item=item, vote=VoteType.FOR
            )

    def rate(self, party: Party) -> float:
        calculate_party_participation_rate()
        party.refresh_from_db()
        assert party.participation_rate is not None
        return party.participation_rate

    def test_party_formed_later_is_not_penalised(self) -> None:
        self.vote(self.established, self.items)
        newcomer = self.party()
        self.vote(newcomer, self.items[6:])
        self.assertEqual(100.0, self.rate(newcomer))
        self.assertEqual(100.0, self.rate(self.established))

    def test_missed_votes_after_start_count(self) -> None:
        self.vote(self.established, self.items)
        newcomer = self.party()
        # Starts at item 2, then misses items 4 and 5: 6 of 8.
        self.vote(newcomer, self.items[2:4] + self.items[6:])
        self.assertEqual(75.0, self.rate(newcomer))

    def test_party_that_stopped_voting_drops(self) -> None:
        self.vote(self.established, self.items)
        former = self.party()
        self.vote(former, self.items[:4])
        self.assertEqual(40.0, self.rate(former))

    def test_items_without_votes_are_ignored(self) -> None:
        # Items whose votes are not published yet do not count.
        self.vote(self.established, self.items[:5])
        self.assertEqual(100.0, self.rate(self.established))

    def test_items_sharing_a_timestamp_are_counted_separately(self) -> None:
        same_time = self.items[0].date
        twins = [self.item(same_time) for _ in range(3)]
        self.vote(self.established, self.items + twins)
        partial = self.party()
        self.vote(partial, self.items)
        self.assertAlmostEqual(100.0 * 10 / 13, self.rate(partial))


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

    def test_duplicate_party_score_raises_integrity_error(self) -> None:
        run_pca_analysis(n_components=3)
        existing = PCAComponentPartyScore.objects.first()
        assert existing is not None
        with self.assertRaises(IntegrityError):
            PCAComponentPartyScore.objects.create(
                component=existing.component,
                party=existing.party,
                score=0.0,
            )

    def test_duplicate_item_loading_raises_integrity_error(self) -> None:
        run_pca_analysis(n_components=3)
        existing = PCAItemLoading.objects.first()
        assert existing is not None
        with self.assertRaises(IntegrityError):
            PCAItemLoading.objects.create(
                component=existing.component,
                parliamentary_item=existing.parliamentary_item,
                loading=0.0,
            )


class TestGeneratePCAObject(TestCase):
    def setUp(self) -> None:
        rng = np.random.default_rng(seed=0)
        self.parties = ["A", "B", "C", "D", "E", "F"]
        self.items = list(range(100, 120))
        self.df = pd.DataFrame(
            rng.choice([-1, 0, 1], size=(len(self.parties), len(self.items))),
            index=self.parties,
            columns=self.items,
        )

    def test_party_scores_per_component(self) -> None:
        model = generate_pca_object(self.df, self.parties, n_components=3)
        scores = model.results["PC"]
        self.assertEqual(self.parties, list(scores.index))
        self.assertEqual(["PC1", "PC2", "PC3"], list(scores.columns))

    def test_loadings_per_item(self) -> None:
        model = generate_pca_object(self.df, self.parties, n_components=3)
        loadings = model.results["loadings"]
        self.assertEqual(["PC1", "PC2", "PC3"], list(loadings.index))
        self.assertEqual(self.items, list(loadings.columns))

    def test_variance_ratio_is_valid_and_descending(self) -> None:
        model = generate_pca_object(self.df, self.parties, n_components=3)
        variance = list(model.results["variance_ratio"])
        self.assertEqual(3, len(variance))
        self.assertTrue(all(0 <= v <= 1 for v in variance))
        self.assertLessEqual(sum(variance), 1 + 1e-9)
        self.assertEqual(sorted(variance, reverse=True), variance)

    def test_n_components_is_respected(self) -> None:
        model = generate_pca_object(self.df, self.parties, n_components=2)
        self.assertEqual(["PC1", "PC2"], list(model.results["PC"].columns))


class TestRunFullAnalysis(TestCase):
    def setUp(self) -> None:
        self.parties = generate_parties()
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=self.parties,
            calculate_participation_rate=False,
        )

    def test_calculates_participation_rates(self) -> None:
        self.assertFalse(
            Party.objects.filter(participation_rate__isnull=False).exists()
        )
        run_full_analysis(n_components=3, stdout=StringIO())
        for party in Party.objects.all():
            self.assertEqual(100.0, party.participation_rate)

    def test_creates_analysis_with_requested_components(self) -> None:
        run_full_analysis(n_components=2, stdout=StringIO())
        analysis = PCAAnalysis.objects.get()
        self.assertEqual(2, analysis.components.count())

    def test_reports_progress_to_stdout(self) -> None:
        stdout = StringIO()
        run_full_analysis(n_components=3, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("Calculating party participation rates", output)
        self.assertIn("Running PCA analysis", output)
        self.assertIn("PCA analysis completed", output)
