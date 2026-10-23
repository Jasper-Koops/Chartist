from datetime import date, datetime, timedelta, timezone
from io import StringIO

import numpy as np
import pandas as pd
from analyzer.analysis import (
    generate_pca_object,
    project_parties,
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
    AgreementMatrix,
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

    def test_non_participation_reduces_participation(
        self,
    ) -> None:
        party = self.parties.first()
        positions = [
            VoteType.FOR,
            VoteType.AGAINST,
            VoteType.SPLIT,
            VoteType.ABSTAIN,
            VoteType.ABSTAIN,
        ]
        for item, position in zip(self.items, positions):
            PartyVoteFactory(
                party=party, parliamentary_item=item, vote=position
            )
        calculate_party_participation_rate()
        party.refresh_from_db()
        self.assertEqual(60.0, party.participation_rate)

    def test_party_with_only_absences_has_zero_participation(self) -> None:
        party = self.parties.first()
        for item in self.items:
            PartyVoteFactory(
                party=party, parliamentary_item=item, vote=VoteType.ABSTAIN
            )
        calculate_party_participation_rate()
        party.refresh_from_db()
        self.assertEqual(0.0, party.participation_rate)

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

    def test_start_uses_voting_date_not_modified_date(self) -> None:
        # Voted in January, but the record was last edited in June.
        early = ParliamentaryItemFactory(
            vote_date=date(2026, 1, 5),
            date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        later = ParliamentaryItemFactory(
            vote_date=date(2026, 2, 5),
            date=datetime(2026, 2, 5, tzinfo=timezone.utc),
        )
        established = self.party()
        self.vote(established, [early, later])
        newcomer = self.party()
        self.vote(newcomer, [later])
        # Only `later` came after the newcomer's first vote.
        self.assertEqual(100.0, self.rate(newcomer))

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
        prepared = prepare_df(log=self.log)
        self.assertEqual(prepared.fit.shape, (15, 5))
        self.assertTrue(prepared.projected.empty)
        items: QuerySet[ParliamentaryItem] = ParliamentaryItem.objects.filter(
            id__in=prepared.fit.columns
        )
        self.assertEqual(5, items.count())

    def test_absence_removes_motion_from_fit_but_split_remains(self) -> None:
        parties = [PartyFactory() for _ in range(3)]
        items = [
            ParliamentaryItemFactory(
                vote_date=date(2026, 1, 1) + timedelta(days=i)
            )
            for i in range(100)
        ]
        for party in parties:
            for item in items:
                PartyVoteFactory(
                    party=party, parliamentary_item=item, vote=VoteType.FOR
                )
        from scraper.models import PartyVote

        PartyVote.objects.filter(
            party=parties[0], parliamentary_item=items[0]
        ).update(vote=VoteType.ABSTAIN)
        PartyVote.objects.filter(
            party=parties[0], parliamentary_item=items[1]
        ).update(vote=VoteType.SPLIT)
        calculate_party_participation_rate()
        prepared = prepare_df(log=self.log)
        self.assertEqual((3, 99), prepared.fit.shape)
        self.assertNotIn(items[0].id, prepared.fit.columns)
        self.assertEqual(
            0, prepared.fit.loc[parties[0].abbreviation, items[1].id]
        )
        self.assertFalse(prepared.fit.isna().any().any())

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
        prepared = prepare_df(log=self.log)
        # One less party
        self.assertEqual(prepared.fit.shape, (14, 5))


class TestLateParty(TestCase):
    """A party that started later is projected, not used to fit the axes."""

    def setUp(self) -> None:
        self.parties = generate_parties()
        self.items = [
            ParliamentaryItemFactory(
                vote_date=date(2026, 1, 1) + timedelta(days=i)
            )
            for i in range(40)
        ]
        generate_party_votes(
            parliamentary_items=ParliamentaryItem.objects.all(),
            parties=self.parties,
            calculate_participation_rate=False,
        )
        self.late: Party = PartyFactory()

    def vote_late(self, count: int) -> None:
        for item in self.items[-count:]:
            PartyVoteFactory(
                party=self.late, parliamentary_item=item, vote=VoteType.FOR
            )
        calculate_party_participation_rate()

    def test_axes_cover_every_motion(self) -> None:
        self.vote_late(25)
        prepared = prepare_df(log=AnalysisLogger(logger, {}))
        self.assertEqual(40, prepared.fit.shape[1])
        self.assertNotIn(self.late.abbreviation, prepared.labels)
        self.assertEqual(
            [self.late.abbreviation], list(prepared.projected.index)
        )
        self.assertEqual(15, int(prepared.projected.isna().sum(axis=1).iloc[0]))

    def test_late_party_gets_scores(self) -> None:
        self.vote_late(25)
        run_pca_analysis(n_components=3)
        self.assertEqual(
            3, PCAComponentPartyScore.objects.filter(party=self.late).count()
        )
        self.assertEqual(40 * 3, PCAItemLoading.objects.count())

    def test_projection_minimum_excludes_absence_but_counts_split(self) -> None:
        from scraper.models import PartyVote

        self.vote_late(20)
        entry = PartyVote.objects.get(
            party=self.late, parliamentary_item=self.items[-1]
        )
        entry.vote = VoteType.ABSTAIN
        entry.save(update_fields=["vote"])
        calculate_party_participation_rate()
        self.assertNotIn(
            self.late.abbreviation,
            prepare_df(log=AnalysisLogger(logger, {})).projected.index,
        )
        entry.vote = VoteType.SPLIT
        entry.save(update_fields=["vote"])
        calculate_party_participation_rate()
        prepared = prepare_df(log=AnalysisLogger(logger, {}))
        self.assertEqual(
            20, prepared.projected.loc[self.late.abbreviation].notna().sum()
        )
        self.assertEqual(
            0, prepared.projected.loc[self.late.abbreviation, self.items[-1].id]
        )

    def test_short_ended_history_without_successor_is_projected(self) -> None:
        for item in self.items[:20]:
            PartyVoteFactory(
                party=self.late, parliamentary_item=item, vote=VoteType.FOR
            )
        calculate_party_participation_rate()
        self.late.refresh_from_db()
        self.assertEqual(50.0, self.late.participation_rate)
        run_pca_analysis(n_components=3)
        self.assertEqual(
            3, PCAComponentPartyScore.objects.filter(party=self.late).count()
        )

    def test_too_few_votes_is_left_out(self) -> None:
        self.vote_late(10)
        run_pca_analysis(n_components=3)
        self.assertFalse(
            PCAComponentPartyScore.objects.filter(party=self.late).exists()
        )
        self.assertEqual(45, PCAComponentPartyScore.objects.count())


class TestProjectParties(TestCase):
    def setUp(self) -> None:
        # Rows lying exactly in a 2D plane, so 3 components capture them
        # completely.
        rng = np.random.default_rng(seed=1)
        positions = rng.normal(size=(8, 2))
        directions = rng.normal(size=(2, 30))
        self.df = pd.DataFrame(
            positions @ directions + rng.normal(size=30),
            index=list("ABCDEFGH"),
            columns=range(30),
        )
        self.model = generate_pca_object(
            self.df, list(self.df.index), n_components=3
        )

    def test_full_row_equals_its_score(self) -> None:
        projected = project_parties(self.model, self.df.iloc[[0]])
        np.testing.assert_allclose(
            self.model.results["PC"].iloc[0].to_numpy(),
            projected.iloc[0].to_numpy(),
            atol=1e-8,
        )

    def test_missing_votes_do_not_pull_to_the_centre(self) -> None:
        # Half the votes hidden: the same position, where filling in the
        # average would shrink it.
        row = self.df.iloc[[2]].copy()
        row.iloc[0, :15] = np.nan
        projected = project_parties(self.model, row)
        np.testing.assert_allclose(
            self.model.results["PC"].iloc[2].to_numpy()[:2],
            projected.iloc[0].to_numpy()[:2],
            atol=1e-8,
        )


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

    def test_predecessor_receives_no_scores_and_successor_keeps_history(
        self,
    ) -> None:
        from scraper.models import PartySuccession

        old = PartyFactory()
        successor = self.parties.first()
        PartySuccession.objects.create(
            predecessor=old,
            successor=successor,
            date=date(2026, 1, 1),
            member_overlap=1,
        )
        for item in ParliamentaryItem.objects.all():
            PartyVoteFactory(
                party=old, parliamentary_item=item, vote=VoteType.FOR
            )
        run_full_analysis(n_components=3, stdout=StringIO())
        self.assertFalse(
            PCAComponentPartyScore.objects.filter(party=old).exists()
        )
        self.assertEqual(
            3, PCAComponentPartyScore.objects.filter(party=successor).count()
        )
        self.assertTrue(Party.objects.filter(pk=old.pk).exists())
        self.assertTrue(
            AgreementMatrix.objects.get().agreements.filter(party=old).exists()
        )

    def test_creates_analysis_with_requested_components(self) -> None:
        run_full_analysis(n_components=2, stdout=StringIO())
        analysis = PCAAnalysis.objects.get()
        self.assertEqual(2, analysis.components.count())

    def test_creates_agreement_matrix(self) -> None:
        run_full_analysis(n_components=3, stdout=StringIO())
        matrix = AgreementMatrix.objects.get()
        n_parties = self.parties.count()
        self.assertEqual(
            n_parties * (n_parties - 1),
            matrix.agreements.filter(month__isnull=True).count(),
        )

    def test_reports_progress_to_stdout(self) -> None:
        stdout = StringIO()
        run_full_analysis(n_components=3, stdout=stdout)
        output = stdout.getvalue()
        self.assertIn("Calculating party participation rates", output)
        self.assertIn("Running PCA analysis", output)
        self.assertIn("PCA analysis completed", output)
        self.assertIn("Agreement matrix completed", output)
