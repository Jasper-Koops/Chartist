from datetime import date, datetime
from datetime import timezone as dt_timezone

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

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
        return matrix.agreements.filter(month__isnull=True).get(
            party=p, other_party=q
        )

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
        self.assertEqual(
            3 * 2, matrix.agreements.filter(month__isnull=True).count()
        )
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
        self.assertEqual(
            0, matrix.agreements.filter(month__isnull=True).count()
        )

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


class TestMonthlyAgreement(TestCase):
    """Monthly rows next to the overall row, keyed by voting month."""

    def setUp(self) -> None:
        self.a, self.b = make_party(), make_party()
        # January: agree on 2 of 2. February: agree on 1 of 2.
        days = [
            date(2026, 1, 5),
            date(2026, 1, 20),
            date(2026, 2, 3),
            date(2026, 2, 9),
        ]
        self.items = [ParliamentaryItemFactory(vote_date=day) for day in days]
        for item, (va, vb) in zip(self.items, [(F, F), (A, A), (F, F), (F, A)]):
            PartyVoteFactory(party=self.a, parliamentary_item=item, vote=va)
            PartyVoteFactory(party=self.b, parliamentary_item=item, vote=vb)

    def monthly(self, matrix: AgreementMatrix) -> dict[date, PartyAgreement]:
        return {
            row.month: row
            for row in matrix.agreements.filter(
                party=self.a, other_party=self.b, month__isnull=False
            )
            if row.month is not None
        }

    def test_agreement_per_month(self) -> None:
        months = self.monthly(run_agreement_analysis())
        self.assertEqual([date(2026, 1, 1), date(2026, 2, 1)], sorted(months))
        self.assertEqual(2, months[date(2026, 1, 1)].shared_motions)
        self.assertAlmostEqual(1.0, months[date(2026, 1, 1)].agreement or 0)
        self.assertAlmostEqual(0.5, months[date(2026, 2, 1)].agreement or 0)

    def test_overall_row_is_kept(self) -> None:
        overall = (
            run_agreement_analysis()
            .agreements.filter(month__isnull=True)
            .get(party=self.a, other_party=self.b)
        )
        self.assertEqual(4, overall.shared_motions)
        self.assertAlmostEqual(0.75, overall.agreement or 0)

    def test_falls_back_to_modified_date_without_vote_date(self) -> None:
        item = ParliamentaryItemFactory(
            vote_date=None,
            date=datetime(2026, 3, 10, 12, tzinfo=dt_timezone.utc),
        )
        PartyVoteFactory(party=self.a, parliamentary_item=item, vote=F)
        PartyVoteFactory(party=self.b, parliamentary_item=item, vote=F)
        self.assertIn(date(2026, 3, 1), self.monthly(run_agreement_analysis()))

    def test_months_without_shared_motions_are_not_stored(self) -> None:
        other = make_party()
        PartyVoteFactory(party=other, parliamentary_item=self.items[0], vote=F)
        matrix = run_agreement_analysis()
        months = set(
            matrix.agreements.filter(
                party=self.a, other_party=other, month__isnull=False
            ).values_list("month", flat=True)
        )
        self.assertEqual({date(2026, 1, 1)}, months)

    def test_matrix_endpoint_only_returns_overall_rows(self) -> None:
        matrix = run_agreement_analysis()
        response = APIClient().get(
            reverse("agreementmatrix-detail", args=[matrix.id])
        )
        self.assertEqual(2, len(response.data["agreements"]))


class TestAgreementTimelineEndpoint(APITestCase):
    def setUp(self) -> None:
        self.a, self.b = make_party(), make_party()
        for day, (va, vb) in [
            (date(2026, 1, 5), (F, F)),
            (date(2026, 2, 3), (F, A)),
        ]:
            item = ParliamentaryItemFactory(vote_date=day)
            PartyVoteFactory(party=self.a, parliamentary_item=item, vote=va)
            PartyVoteFactory(party=self.b, parliamentary_item=item, vote=vb)

    def url(self, party: Party) -> str:
        return reverse("party-agreement-timeline", args=[party.id])

    def test_series_per_other_party(self) -> None:
        matrix = run_agreement_analysis()
        response = self.client.get(self.url(self.a))
        self.assertEqual(200, response.status_code)
        data = response.data
        self.assertEqual(matrix.id, data["matrix"])
        self.assertEqual([date(2026, 1, 1), date(2026, 2, 1)], data["months"])
        [series] = data["series"]
        self.assertEqual(self.b.id, series["party"])
        self.assertEqual(
            [1.0, 0.0], [point["agreement"] for point in series["points"]]
        )

    def test_uses_newest_matrix(self) -> None:
        run_agreement_analysis()
        newest = run_agreement_analysis()
        self.assertEqual(
            newest.id, self.client.get(self.url(self.a)).data["matrix"]
        )

    def test_no_matrix_returns_404(self) -> None:
        self.assertEqual(404, self.client.get(self.url(self.a)).status_code)

    def test_unknown_party_returns_404(self) -> None:
        run_agreement_analysis()
        response = self.client.get(
            reverse("party-agreement-timeline", args=[999999])
        )
        self.assertEqual(404, response.status_code)


class TestStatusEndpoint(APITestCase):
    def test_reports_freshness(self) -> None:
        a, b = make_party(), make_party()
        for day in [date(2026, 1, 5), date(2026, 3, 9)]:
            item = ParliamentaryItemFactory(vote_date=day)
            PartyVoteFactory(party=a, parliamentary_item=item, vote=F)
            PartyVoteFactory(party=b, parliamentary_item=item, vote=F)
        ParliamentaryItemFactory(vote_date=date(2026, 4, 1))  # no votes yet
        matrix = run_agreement_analysis()

        data = self.client.get(reverse("status")).data
        self.assertEqual(date(2026, 3, 9), data["latest_vote_date"])
        self.assertEqual(2, data["motions_with_votes"])
        self.assertIsNone(data["latest_analysis_at"])
        self.assertEqual(matrix.created_at, data["latest_agreement_matrix_at"])

    def test_empty_database(self) -> None:
        data = self.client.get(reverse("status")).data
        self.assertIsNone(data["latest_vote_date"])
        self.assertEqual(0, data["motions_with_votes"])


class TestPartyDetailPage(TestCase):
    def test_shows_party(self) -> None:
        party = make_party()
        response = self.client.get(reverse("party-detail", args=[party.id]))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, party.name)

    def test_unknown_party_is_404(self) -> None:
        response = self.client.get(reverse("party-detail", args=[999999]))
        self.assertEqual(404, response.status_code)
