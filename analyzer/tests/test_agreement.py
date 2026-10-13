from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from analyzer.agreement import run_agreement_analysis
from analyzer.models import AgreementMatrix, PartyAgreement
from scraper.models import ParliamentaryItem, Party, VoteType
from scraper.tests.factories import (
    ParliamentaryItemFactory,
    PartyFactory,
    PartyVoteFactory,
)


def make_party() -> Party:
    party: Party = PartyFactory()
    return party


def make_item() -> ParliamentaryItem:
    item: ParliamentaryItem = ParliamentaryItemFactory()
    return item


def cast(votes: dict[Party, list[str | None]]) -> None:
    """Votes per party per item; None means no vote on that item."""
    n_items = len(next(iter(votes.values())))
    items = [make_item() for _ in range(n_items)]
    for party, party_votes in votes.items():
        for item, vote in zip(items, party_votes):
            if vote is not None:
                PartyVoteFactory(
                    party=party, parliamentary_item=item, vote=vote
                )


F, A, X = VoteType.FOR, VoteType.AGAINST, VoteType.ABSTAIN


class TestAgreementAnalysis(TestCase):
    def setUp(self) -> None:
        self.a, self.b, self.c = make_party(), make_party(), make_party()

    def pair(
        self, matrix: AgreementMatrix, p: Party, q: Party
    ) -> PartyAgreement:
        return matrix.agreements.get(party=p, other_party=q)

    def value(self, pair: PartyAgreement) -> float:
        assert pair.agreement is not None
        return pair.agreement

    def test_agreement_is_share_of_same_votes(self) -> None:
        cast({self.a: [F, F, A, A], self.b: [F, A, A, A], self.c: [A, A, F, F]})
        matrix = run_agreement_analysis()

        ab = self.pair(matrix, self.a, self.b)
        self.assertEqual(4, ab.shared_motions)
        self.assertAlmostEqual(0.75, self.value(ab))
        self.assertAlmostEqual(
            0.0, self.value(self.pair(matrix, self.a, self.c))
        )

    def test_symmetric_and_stored_both_ways(self) -> None:
        cast({self.a: [F, A, F], self.b: [F, F, F], self.c: [A, A, A]})
        matrix = run_agreement_analysis()

        # Every ordered pair of different parties, no diagonal.
        self.assertEqual(3 * 2, matrix.agreements.count())
        for p, q in [(self.a, self.b), (self.a, self.c), (self.b, self.c)]:
            self.assertEqual(
                self.pair(matrix, p, q).agreement,
                self.pair(matrix, q, p).agreement,
            )

    def test_not_taking_part_is_not_a_vote(self) -> None:
        cast({self.a: [F, F, X], self.b: [F, A, A], self.c: [F, F, F]})
        ab = self.pair(run_agreement_analysis(), self.a, self.b)
        self.assertEqual(2, ab.shared_motions)
        self.assertAlmostEqual(0.5, self.value(ab))

    def test_only_shared_motions_count(self) -> None:
        # c only exists for the last two items, e.g. after a split.
        cast(
            {
                self.a: [F, A, F, F],
                self.b: [A, A, F, A],
                self.c: [None, None, F, F],
            }
        )
        matrix = run_agreement_analysis()
        ac = self.pair(matrix, self.a, self.c)
        self.assertEqual(2, ac.shared_motions)
        self.assertAlmostEqual(1.0, self.value(ac))

    def test_parties_without_shared_motions_have_no_agreement(self) -> None:
        # e.g. a party and its renamed successor.
        cast(
            {
                self.a: [F, A, None, None],
                self.b: [None, None, F, A],
                self.c: [F, F, F, F],
            }
        )
        ab = self.pair(run_agreement_analysis(), self.a, self.b)
        self.assertEqual(0, ab.shared_motions)
        self.assertIsNone(ab.agreement)

    def test_no_votes_gives_empty_matrix(self) -> None:
        matrix = run_agreement_analysis()
        self.assertEqual(0, matrix.agreements.count())

    def test_each_run_stores_a_new_matrix(self) -> None:
        cast({self.a: [F], self.b: [F]})
        run_agreement_analysis()
        run_agreement_analysis()
        self.assertEqual(2, AgreementMatrix.objects.count())


class TestAgreementMatrixViewSet(APITestCase):
    def setUp(self) -> None:
        self.a, self.b = make_party(), make_party()
        cast({self.a: [F, A], self.b: [F, F]})
        self.old = run_agreement_analysis()
        self.latest = run_agreement_analysis()

    def test_newest_matrix_first(self) -> None:
        response = self.client.get(
            reverse("agreementmatrix-list"), {"limit": 1}
        )
        self.assertEqual(200, response.status_code)
        results = response.data["results"]
        self.assertEqual([self.latest.id], [m["id"] for m in results])

    def test_matrix_lists_parties_and_pairs(self) -> None:
        response = self.client.get(
            reverse("agreementmatrix-detail", args=[self.latest.id])
        )
        data = response.data
        self.assertEqual(
            sorted([self.a.abbreviation, self.b.abbreviation]),
            [p["abbreviation"] for p in data["parties"]],
        )
        pair = next(
            a
            for a in data["agreements"]
            if a["party"] == self.a.id and a["other_party"] == self.b.id
        )
        self.assertAlmostEqual(0.5, pair["agreement"])
        self.assertEqual(2, pair["shared_motions"])
