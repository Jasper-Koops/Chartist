import logging
from datetime import date, datetime, timedelta, timezone

from django.test import TestCase

from analyzer.agreement import run_agreement_analysis
from analyzer.analysis import calculate_party_participation_rate
from analyzer.utils import AnalysisLogger, generate_dataframe
from analyzer.votes import lineage_pairs, party_votes
from scraper.models import ParliamentaryItem, Party, PartySuccession, VoteType
from scraper.tests.factories import (
    ParliamentaryItemFactory,
    PartyFactory,
    PartyVoteFactory,
)

F, A = VoteType.FOR, VoteType.AGAINST


class SuccessionTestCase(TestCase):
    """
    Six items, one per day. `old` votes on items 0-2 and is continued by
    `new`, which votes on items 3-5. `other` votes on everything.
    """

    def setUp(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.items = [self.item(start + timedelta(days=d)) for d in range(6)]
        self.old, self.new, self.other = (
            self.party(),
            self.party(),
            self.party(),
        )
        self.vote(self.old, self.items[:3], [F, A, F])
        self.vote(self.new, self.items[3:], [A, A, F])
        self.vote(self.other, self.items, [F, A, A, A, A, F])
        self.succession = PartySuccession.objects.create(
            predecessor=self.old,
            successor=self.new,
            date=date(2026, 1, 4),
            member_overlap=0.95,
        )

    def item(self, when: datetime) -> ParliamentaryItem:
        item: ParliamentaryItem = ParliamentaryItemFactory(date=when)
        return item

    def party(self) -> Party:
        party: Party = PartyFactory()
        return party

    def vote(
        self, party: Party, items: list[ParliamentaryItem], votes: list[str]
    ) -> None:
        for item, vote in zip(items, votes):
            PartyVoteFactory(party=party, parliamentary_item=item, vote=vote)


class TestPartyVotes(SuccessionTestCase):
    def test_successor_inherits_predecessor_votes(self) -> None:
        votes = party_votes()
        self.assertEqual(
            {item.id: v for item, v in zip(self.items, [F, A, F, A, A, F])},
            votes[self.new.id],
        )

    def test_predecessor_keeps_only_its_own_votes(self) -> None:
        self.assertEqual(
            {item.id for item in self.items[:3]},
            set(party_votes()[self.old.id]),
        )

    def test_own_vote_wins_over_inherited(self) -> None:
        # Both voted on item 2, e.g. around the succession date.
        PartyVoteFactory(
            party=self.new, parliamentary_item=self.items[2], vote=A
        )
        self.assertEqual(A, party_votes()[self.new.id][self.items[2].id])

    def test_chain_is_followed(self) -> None:
        newest = self.party()
        PartySuccession.objects.create(
            predecessor=self.new,
            successor=newest,
            date=date(2026, 2, 1),
            member_overlap=1.0,
        )
        self.assertEqual(6, len(party_votes()[newest.id]))
        self.assertIn((self.old.id, newest.id), lineage_pairs())

    def test_without_succession_nothing_is_inherited(self) -> None:
        self.succession.delete()
        self.assertEqual(3, len(party_votes()[self.new.id]))


class TestSuccessionInAnalysis(SuccessionTestCase):
    def test_successor_participation_includes_inherited_history(self) -> None:
        calculate_party_participation_rate()
        for party in (self.old, self.new, self.other):
            party.refresh_from_db()
        self.assertEqual(100.0, self.new.participation_rate)
        # The predecessor stopped voting halfway.
        self.assertEqual(50.0, self.old.participation_rate)

    def test_inherited_absence_and_split_keep_their_meaning(self) -> None:
        from scraper.models import PartyVote

        PartyVote.objects.filter(
            party=self.old, parliamentary_item=self.items[0]
        ).update(vote=VoteType.ABSTAIN)
        PartyVote.objects.filter(
            party=self.old, parliamentary_item=self.items[1]
        ).update(vote=VoteType.SPLIT)
        # An explicit absence must also override a predecessor's FOR.
        PartyVoteFactory(
            party=self.new,
            parliamentary_item=self.items[2],
            vote=VoteType.ABSTAIN,
        )
        calculate_party_participation_rate()
        self.new.refresh_from_db()
        self.old.refresh_from_db()
        self.assertAlmostEqual(400 / 6, self.new.participation_rate)
        self.assertEqual(100.0, self.new.record_coverage)
        self.assertAlmostEqual(200 / 6, self.old.participation_rate)
        df = generate_dataframe(
            log=AnalysisLogger(logging.getLogger(), {})
        ).set_index("Motion ID")
        self.assertTrue(
            df.loc[[self.items[0].id, self.items[2].id], self.new.abbreviation]
            .isna()
            .all()
        )
        self.assertEqual(0, df.loc[self.items[1].id, self.new.abbreviation])

    def test_pca_input_uses_inherited_votes(self) -> None:
        calculate_party_participation_rate()
        df = generate_dataframe(log=AnalysisLogger(logging.getLogger(), {}))
        self.assertIn(self.new.abbreviation, df.columns)
        self.assertNotIn(self.old.abbreviation, df.columns)
        # No missing votes: all six items are usable.
        self.assertEqual(6, len(df.dropna()))

    def test_matrix_keeps_both_parties_and_skips_their_pair(self) -> None:
        matrix = run_agreement_analysis()
        pair = matrix.agreements.filter(month__isnull=True).get(
            party=self.old, other_party=self.new
        )
        self.assertIsNone(pair.agreement)
        self.assertEqual(0, pair.shared_motions)

        # The successor is compared over the inherited history too.
        new_other = matrix.agreements.filter(month__isnull=True).get(
            party=self.new, other_party=self.other
        )
        old_other = matrix.agreements.filter(month__isnull=True).get(
            party=self.old, other_party=self.other
        )
        self.assertEqual(6, new_other.shared_motions)
        self.assertEqual(3, old_other.shared_motions)

    def test_lineage_pair_has_no_monthly_rows(self) -> None:
        matrix = run_agreement_analysis()
        self.assertFalse(
            matrix.agreements.filter(
                party=self.old, other_party=self.new, month__isnull=False
            ).exists()
        )
        # The successor does get monthly rows with other parties.
        self.assertTrue(
            matrix.agreements.filter(
                party=self.new, other_party=self.other, month__isnull=False
            ).exists()
        )


class TestPartyVotesSubset(SuccessionTestCase):
    def test_only_requested_parties_are_loaded(self) -> None:
        votes = party_votes([self.other.id])
        self.assertEqual({self.other.id}, set(votes))
        self.assertEqual(6, len(votes[self.other.id]))

    def test_predecessors_are_loaded_for_inheritance(self) -> None:
        votes = party_votes([self.new.id])
        # The successor still inherits the predecessor's votes.
        self.assertEqual(party_votes()[self.new.id], votes[self.new.id])

    def test_chain_is_followed_for_a_subset(self) -> None:
        newest = self.party()
        PartySuccession.objects.create(
            predecessor=self.new,
            successor=newest,
            date=date(2026, 2, 1),
            member_overlap=1.0,
        )
        self.assertEqual(6, len(party_votes([newest.id])[newest.id]))
