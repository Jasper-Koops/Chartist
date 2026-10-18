from datetime import date
from collections.abc import Iterable
from typing import Any

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from analyzer.analysis import run_pca_analysis
from analyzer.compare import pair_votes, related_items, summarize
from analyzer.models import PCAAnalysis
from analyzer.votes import party_votes_with_sources
from scraper.models import ParliamentaryItem, Party, PartySuccession, VoteType
from scraper.tests.factories import (
    ParliamentaryItemFactory,
    PartyFactory,
    PartyVoteFactory,
)
from scraper.tests.utils.testing_utils import (
    generate_parliamentary_items,
    generate_parties,
    generate_party_votes,
)

F, A, X = VoteType.FOR, VoteType.AGAINST, VoteType.ABSTAIN


def make_party() -> Party:
    party: Party = PartyFactory()
    return party


class PairData:
    """Five items, newest last: a and b agree on 2, differ on 2, one abstain."""

    def make_pair(self) -> None:
        self.a, self.b = make_party(), make_party()
        votes = [(F, F), (A, A), (F, A), (A, F), (F, X)]
        self.items: list[ParliamentaryItem] = []
        for day, (va, vb) in enumerate(votes, start=1):
            item: ParliamentaryItem = ParliamentaryItemFactory(
                vote_date=date(2026, 1, day), title=f"Motie {day}"
            )
            self.items.append(item)
            PartyVoteFactory(party=self.a, parliamentary_item=item, vote=va)
            PartyVoteFactory(party=self.b, parliamentary_item=item, vote=vb)


class TestCompare(PairData, TestCase):
    def setUp(self) -> None:
        self.make_pair()

    def test_summary(self) -> None:
        summary = summarize(pair_votes(self.a.id, self.b.id))
        self.assertEqual(4, summary.shared_motions)
        self.assertEqual(2, summary.agreed)
        self.assertAlmostEqual(0.5, summary.agreement or 0)
        self.assertEqual(1, summary.party_for_other_against)
        self.assertEqual(1, summary.party_against_other_for)
        self.assertFalse(summary.same_lineage)

    def ids(self, indexes: Iterable[int]) -> list[int]:
        return sorted(self.items[i].id for i in indexes)

    def test_related_items(self) -> None:
        votes, other, *_ = pair_votes(self.a.id, self.b.id)
        self.assertEqual(
            self.ids([2, 3]), sorted(related_items(votes, other, "differed"))
        )
        self.assertEqual(
            self.ids([0, 1]), sorted(related_items(votes, other, "agreed"))
        )
        self.assertEqual(
            self.ids(range(5)), sorted(related_items(votes, other, "all"))
        )
        with self.assertRaises(ValueError):
            related_items(votes, other, "bogus")

    def test_successor_compared_on_own_votes(self) -> None:
        PartySuccession.objects.create(
            predecessor=self.a,
            successor=self.b,
            date=date(2026, 1, 1),
            member_overlap=1.0,
        )
        pair = pair_votes(self.b.id, self.a.id)
        self.assertTrue(pair.same_lineage)
        # b's own votes, not a's inherited ones: they still differ on 2.
        summary = summarize(pair)
        self.assertEqual(
            2, summary.party_for_other_against + summary.party_against_other_for
        )


class TestCompareApi(PairData, APITestCase):
    def setUp(self) -> None:
        self.make_pair()

    def test_compare_endpoint(self) -> None:
        url = reverse("party-compare", args=[self.a.id, self.b.id])
        data = self.client.get(url).data
        self.assertEqual(
            self.b.abbreviation, data["other_party"]["abbreviation"]
        )
        self.assertEqual(4, data["shared_motions"])
        self.assertAlmostEqual(0.5, data["agreement"])
        self.assertEqual([], data["timeline"])  # no matrix yet

    def test_motions_differed_by_default_newest_first(self) -> None:
        url = reverse("party-compare-motions", args=[self.a.id, self.b.id])
        results = self.client.get(url).data["results"]
        self.assertEqual(
            [self.items[3].id, self.items[2].id], [m["id"] for m in results]
        )
        self.assertEqual(
            ("Against", "For"),
            (results[0]["party_vote"], results[0]["other_party_vote"]),
        )

    def test_motions_search_and_relation(self) -> None:
        url = reverse("party-compare-motions", args=[self.a.id, self.b.id])
        response = self.client.get(
            url, {"relation": "agreed", "search": "Motie 2"}
        )
        self.assertEqual(
            [self.items[1].id], [m["id"] for m in response.data["results"]]
        )

    def test_invalid_relation(self) -> None:
        url = reverse("party-compare-motions", args=[self.a.id, self.b.id])
        self.assertEqual(
            400, self.client.get(url, {"relation": "x"}).status_code
        )

    def test_unknown_other_party(self) -> None:
        url = reverse("party-compare", args=[self.a.id, 999999])
        self.assertEqual(404, self.client.get(url).status_code)


class TestPairPage(TestCase):
    def test_pair_page(self) -> None:
        a, b = make_party(), make_party()
        response = self.client.get(reverse("pair-detail", args=[a.id, b.id]))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, a.abbreviation)

    def test_same_party_is_404(self) -> None:
        a = make_party()
        response = self.client.get(reverse("pair-detail", args=[a.id, a.id]))
        self.assertEqual(404, response.status_code)


class TestComponentBreakdown(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(12),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)
        self.component = PCAAnalysis.objects.get().components.get(number=1)

    def breakdown(self, **params: str) -> dict[str, Any]:
        url = reverse("pcacomponent-breakdown", args=[self.component.id])
        data: dict[str, Any] = self.client.get(url, params).data
        return data

    def test_parties_sorted_by_score(self) -> None:
        scores = [p["score"] for p in self.breakdown()["parties"]]
        self.assertEqual(15, len(scores))
        self.assertEqual(sorted(scores, reverse=True), scores)

    def test_strongest_loadings_per_side(self) -> None:
        data = self.breakdown(limit="3")
        positive = [m["loading"] for m in data["positive"]]
        negative = [m["loading"] for m in data["negative"]]
        self.assertEqual(3, len(positive))
        self.assertEqual(sorted(positive, reverse=True), positive)
        self.assertEqual(sorted(negative), negative)
        all_loadings = list(
            self.component.item_loadings.values_list("loading", flat=True)
        )
        self.assertAlmostEqual(max(all_loadings), positive[0])
        self.assertAlmostEqual(min(all_loadings), negative[0])
        self.assertGreaterEqual(data["tied_at_strongest_positive"], 1)

    def test_invalid_limit(self) -> None:
        url = reverse("pcacomponent-breakdown", args=[self.component.id])
        self.assertEqual(400, self.client.get(url, {"limit": "x"}).status_code)

    def test_component_page(self) -> None:
        self.assertEqual(
            200,
            self.client.get(reverse("component-detail", args=[1])).status_code,
        )


class TestInheritedVoteLabels(APITestCase):
    """Votes a successor inherits are labelled with the predecessor."""

    def setUp(self) -> None:
        self.old, self.new, self.other = (
            make_party(),
            make_party(),
            make_party(),
        )
        PartySuccession.objects.create(
            predecessor=self.old,
            successor=self.new,
            date=date(2026, 1, 10),
            member_overlap=1.0,
        )
        # Before the rename, only the predecessor voted; after it, only the
        # successor. On the last item both voted: the successor's own wins.
        self.items: list[ParliamentaryItem] = []
        for day, voter in [(1, self.old), (20, self.new), (21, None)]:
            item: ParliamentaryItem = ParliamentaryItemFactory(
                vote_date=date(2026, 1, day)
            )
            self.items.append(item)
            for party in [voter] if voter else [self.old, self.new]:
                PartyVoteFactory(party=party, parliamentary_item=item, vote=F)
            PartyVoteFactory(party=self.other, parliamentary_item=item, vote=A)

    def motions(self, party: Party, other: Party) -> dict[int, Any]:
        url = reverse("party-compare-motions", args=[party.id, other.id])
        results = self.client.get(url, {"relation": "all"}).data["results"]
        return {m["id"]: m for m in results}

    def predecessor(self, party: Party) -> dict[str, Any]:
        return {"id": party.id, "abbreviation": party.abbreviation}

    def test_inherited_vote_names_predecessor(self) -> None:
        motions = self.motions(self.new, self.other)
        first, second, third = (motions[item.id] for item in self.items)
        self.assertEqual(
            ("For", self.predecessor(self.old)),
            (first["party_vote"], first["party_vote_inherited_from"]),
        )
        self.assertIsNone(second["party_vote_inherited_from"])
        self.assertIsNone(third["party_vote_inherited_from"])
        self.assertIsNone(first["other_party_vote_inherited_from"])

    def test_other_side_is_labelled_too(self) -> None:
        first = self.motions(self.other, self.new)[self.items[0].id]
        self.assertEqual(
            self.predecessor(self.old),
            first["other_party_vote_inherited_from"],
        )

    def test_nothing_inherited_within_lineage(self) -> None:
        for motion in self.motions(self.new, self.old).values():
            self.assertIsNone(motion["party_vote_inherited_from"])
            self.assertIsNone(motion["other_party_vote_inherited_from"])

    def test_chain_names_the_party_that_voted(self) -> None:
        newest = make_party()
        PartySuccession.objects.create(
            predecessor=self.new,
            successor=newest,
            date=date(2026, 2, 1),
            member_overlap=1.0,
        )
        _, sources = party_votes_with_sources([newest.id])
        self.assertEqual(
            {
                self.items[0].id: self.old.id,
                self.items[1].id: self.new.id,
                self.items[2].id: self.new.id,
            },
            sources[newest.id],
        )

    def test_party_page_links_both_ways(self) -> None:
        new_page = self.client.get(reverse("party-detail", args=[self.new.id]))
        self.assertContains(new_page, "Continues")
        self.assertContains(new_page, f'href="/party/{self.old.id}/"')
        old_page = self.client.get(reverse("party-detail", args=[self.old.id]))
        self.assertContains(old_page, "Continued as")
        self.assertContains(old_page, f'href="/party/{self.new.id}/"')
        other_page = self.client.get(
            reverse("party-detail", args=[self.other.id])
        )
        self.assertNotContains(other_page, "Continue")
