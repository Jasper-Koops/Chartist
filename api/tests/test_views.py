from datetime import date
from typing import Any

from django.utils import timezone

from django.utils.dateparse import parse_datetime
from rest_framework.test import APITestCase
from django.urls import reverse
from scraper.tests.utils.testing_utils import (
    generate_parties,
    generate_parliamentary_items,
    generate_party_votes,
)
from analyzer.analysis import run_pca_analysis
from analyzer.models import (
    PCAAnalysis,
    PCAComponent,
    PCAComponentPartyScore,
    PCAItemLoading,
)
from scraper.models import (
    ImportRun,
    ImportRunStatus,
    Party,
    ParliamentaryItem,
    PartyVote,
    VoteType,
)
from scraper.tests.factories import ParliamentaryItemFactory


class TestPartyViewSet(APITestCase):
    def setUp(self) -> None:
        generate_parties()

    def test_list_returns_200(self) -> None:
        url = reverse("party-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), Party.objects.all().count())

    def test_filter_by_abbreviation(self) -> None:
        url = reverse("party-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(url, {"abbreviation": party.abbreviation})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["abbreviation"], party.abbreviation)

    def test_filter_by_name(self) -> None:
        url = reverse("party-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(url, {"name": party.name})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], party.name)

    def test_filter_by_id(self) -> None:
        url = reverse("party-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(url, {"id": party.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], party.id)

    def test_ordering_by_abbreviation(self) -> None:
        url = reverse("party-list")
        response = self.client.get(url, {"ordering": "abbreviation"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        abbreviations = [party["abbreviation"] for party in data]
        self.assertEqual(abbreviations, sorted(abbreviations))

    def test_reverse_ordering_by_abbreviation(self) -> None:
        url = reverse("party-list")
        response = self.client.get(url, {"ordering": "-abbreviation"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        abbreviations = [party["abbreviation"] for party in data]
        self.assertEqual(abbreviations, sorted(abbreviations, reverse=True))


class TestPartyVoteViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )

    def test_list_returns_200(self) -> None:
        url = reverse("partyvote-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        party_votes: int = PartyVote.objects.all().count()
        votes: int = party_votes if party_votes <= 100 else 100
        self.assertEqual(len(data), votes)

    def test_filter_by_id(self) -> None:
        url = reverse("partyvote-list")
        party_vote = PartyVote.objects.first()
        assert party_vote is not None
        response = self.client.get(url, {"id": party_vote.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], party_vote.id)

    def test_filter_by_party_id(self) -> None:
        url = reverse("partyvote-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(url, {"party": party.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["party"], party.id)

    def test_filter_by_party_abbreviation(self) -> None:
        url = reverse("partyvote-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(
            url, {"party__abbreviation": party.abbreviation}
        )
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["party"], party.id)

    def test_filter_by_parliamentary_item_id(self) -> None:
        url = reverse("partyvote-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"parliamentary_item": item.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["parliamentary_item"], item.id)

    def test_filter_by_vote(self) -> None:
        url = reverse("partyvote-list")
        response = self.client.get(url, {"vote": VoteType.FOR})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["vote"], VoteType.FOR)

    def test_order_by_party(self) -> None:
        url = reverse("partyvote-list")
        response = self.client.get(url, {"ordering": "party"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        parties = [vote["party"] for vote in data]
        self.assertEqual(parties, sorted(parties))


class TestParliamentaryItemViewSet(APITestCase):
    def setUp(self) -> None:
        generate_parliamentary_items()

    def test_list_returns_200(self) -> None:
        url = reverse("parliamentaryitem-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), ParliamentaryItem.objects.all().count())

    def test_filter_by_title(self) -> None:
        url = reverse("parliamentaryitem-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"title": item.title})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], item.title)

    def test_filter_by_title_contains(self) -> None:
        item_1: ParliamentaryItem = ParliamentaryItemFactory(
            title="Climate Action Plan"
        )
        ParliamentaryItemFactory(title="Education Reform Act")
        url = reverse("parliamentaryitem-list")
        partial_title = item_1.title[:5]
        response = self.client.get(url, {"title__icontains": partial_title})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn(partial_title.lower(), data[0]["title"].lower())

    def test_filter_by_date_gte(self) -> None:
        url = reverse("parliamentaryitem-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"date__gte": item.date.isoformat()})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            row_dt = parse_datetime(row["date"])
            assert row_dt is not None
            self.assertGreaterEqual(row_dt, item.date)

    def test_filter_by_date_lte(self) -> None:
        url = reverse("parliamentaryitem-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"date__lte": item.date.isoformat()})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            row_dt = parse_datetime(row["date"])
            assert row_dt is not None
            self.assertIsNotNone(row_dt)
            self.assertLessEqual(row_dt, item.date)

    def test_filter_by_date_exact(self) -> None:
        url = reverse("parliamentaryitem-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"date": item.date.isoformat()})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            row_dt = parse_datetime(row["date"])
            assert row_dt is not None
            self.assertIsNotNone(row_dt)
            self.assertEqual(row_dt, item.date)

    def test_order_by_date(self) -> None:
        url = reverse("parliamentaryitem-list")
        response = self.client.get(url, {"ordering": "date"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        dates = [parse_datetime(item["date"]) for item in data]
        self.assertEqual(dates, sorted(dates))

    def test_order_by_date_reverse(self) -> None:
        url = reverse("parliamentaryitem-list")
        response = self.client.get(url, {"ordering": "-date"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        dates = [parse_datetime(item["date"]) for item in data]
        self.assertEqual(dates, sorted(dates, reverse=True))


class TestParliamentaryItemText(APITestCase):
    def setUp(self) -> None:
        self.item = ParliamentaryItemFactory(text=["verzoekt de regering"])

    def test_list_excludes_text(self) -> None:
        response = self.client.get(reverse("parliamentaryitem-list"))
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertNotIn("text", data[0])

    def test_detail_includes_text(self) -> None:
        response = self.client.get(
            reverse("parliamentaryitem-detail", args=[self.item.id])
        )
        self.assertEqual(["verzoekt de regering"], response.data["text"])


class TestPCAAnalysisViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_list_returns_200(self) -> None:
        url = reverse("pcaanalysis-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)

    def test_filter_by_id(self) -> None:
        url = reverse("pcaanalysis-list")
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        response = self.client.get(url, {"id": analysis.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], analysis.id)

    def test_filter_by_created_at_gte(self) -> None:
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        url = reverse("pcaanalysis-list")
        response = self.client.get(
            url, {"created_at__gte": analysis.created_at.isoformat()}
        )
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(data), 1)
        for row in data:
            row_dt = parse_datetime(row["created_at"])
            assert row_dt is not None
            self.assertGreaterEqual(row_dt, analysis.created_at)

    def test_filter_by_created_at_lte(self) -> None:
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        url = reverse("pcaanalysis-list")
        response = self.client.get(
            url, {"created_at__lte": analysis.created_at.isoformat()}
        )
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(data), 1)
        for row in data:
            row_dt = parse_datetime(row["created_at"])
            assert row_dt is not None
            self.assertLessEqual(row_dt, analysis.created_at)

    def test_filter_by_created_at_exact(self) -> None:
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        url = reverse("pcaanalysis-list")
        response = self.client.get(
            url, {"created_at": analysis.created_at.isoformat()}
        )
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(data), 1)
        for row in data:
            row_dt = parse_datetime(row["created_at"])
            assert row_dt is not None
            self.assertEqual(row_dt, analysis.created_at)


class TestPCAComponentViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_list_returns_200(self) -> None:
        url = reverse("pcacomponent-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), PCAComponent.objects.count())

    def test_filter_by_analysis(self) -> None:
        url = reverse("pcacomponent-list")
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        response = self.client.get(url, {"analysis": analysis.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data), 3)
        for row in data:
            self.assertEqual(row["analysis"], analysis.id)

    def test_filter_by_number(self) -> None:
        url = reverse("pcacomponent-list")
        response = self.client.get(url, {"number": 1})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["number"], 1)

    def test_response_includes_explained_variance(self) -> None:
        url = reverse("pcacomponent-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        for row in data:
            self.assertIn("explained_variance", row)
            self.assertGreater(row["explained_variance"], 0)


class TestPCAAnalysisSerializerNesting(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_analysis_response_includes_nested_components(self) -> None:
        url = reverse("pcaanalysis-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        analysis_data = data[0]
        self.assertIn("components", analysis_data)
        self.assertEqual(len(analysis_data["components"]), 3)
        for component in analysis_data["components"]:
            self.assertIn("number", component)
            self.assertIn("explained_variance", component)


class TestPartyScoresNesting(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        # Run twice so component ids no longer match component numbers.
        run_pca_analysis(n_components=3)
        run_pca_analysis(n_components=3)

    def test_party_scores_are_keyed_by_component_number(self) -> None:
        url = reverse("party-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        last_analysis = PCAAnalysis.objects.order_by("-created_at").first()
        for party_data in data:
            expected = {
                score.component.number: score.score
                for score in PCAComponentPartyScore.objects.filter(
                    party_id=party_data["id"],
                    component__analysis=last_analysis,
                )
            }
            actual = {
                row["component"]: row["score"]
                for row in party_data["party_scores"]
            }
            self.assertEqual(set(actual), {1, 2, 3})
            self.assertEqual(actual, expected)


class TestKeyParliamentaryItemViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_list_returns_200(self) -> None:
        url = reverse("key-parliamentary-items-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_returns_at_most_10_items(self) -> None:
        url = reverse("key-parliamentary-items-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertLessEqual(len(data), 10)

    def test_items_include_votes_and_loadings(self) -> None:
        url = reverse("key-parliamentary-items-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertGreater(len(data), 0)
        for item in data:
            self.assertIn("votes", item)
            self.assertIn("loadings", item)
            self.assertIn("text", item)

    def _expected_top_ids(self, analysis: PCAAnalysis) -> list[int]:
        totals: dict[int, float] = {}
        for loading in PCAItemLoading.objects.filter(
            component__analysis=analysis
        ):
            item_id = loading.parliamentary_item_id
            totals[item_id] = totals.get(item_id, 0.0) + abs(loading.loading)
        return sorted(totals, key=lambda i: totals[i], reverse=True)[:10]

    def test_returns_top_10_by_total_absolute_loading(self) -> None:
        # 15 items in total, so the top 10 is a real selection.
        new_ids = [ParliamentaryItemFactory().id for _ in range(5)]
        generate_party_votes(
            parliamentary_items=ParliamentaryItem.objects.filter(
                id__in=new_ids
            ),
            parties=Party.objects.all(),
        )
        PCAAnalysis.objects.all().delete()
        run_pca_analysis(n_components=3)
        analysis = PCAAnalysis.objects.get()

        response = self.client.get(reverse("key-parliamentary-items-list"))
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(
            self._expected_top_ids(analysis), [item["id"] for item in data]
        )

    def test_uses_latest_analysis_only(self) -> None:
        old_analysis = PCAAnalysis.objects.get()
        run_pca_analysis(n_components=3)
        latest = PCAAnalysis.objects.exclude(pk=old_analysis.pk).get()
        # Make the old analysis favour a different item than the latest one.
        PCAItemLoading.objects.filter(component__analysis=old_analysis).update(
            loading=0
        )
        outlier = PCAItemLoading.objects.filter(
            component__analysis=old_analysis
        ).first()
        assert outlier is not None
        outlier.loading = 1000
        outlier.save()

        response = self.client.get(reverse("key-parliamentary-items-list"))
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(
            self._expected_top_ids(latest), [item["id"] for item in data]
        )

    def test_no_analysis_returns_404(self) -> None:
        PCAAnalysis.objects.all().delete()
        response = self.client.get(reverse("key-parliamentary-items-list"))
        self.assertEqual(404, response.status_code)

    def test_filter_by_id(self) -> None:
        item_id = ParliamentaryItem.objects.first().id  # type: ignore[union-attr]
        response = self.client.get(
            reverse("key-parliamentary-items-list"), {"id": item_id}
        )
        self.assertEqual(200, response.status_code)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual([item_id], [item["id"] for item in data])

    def test_ordering_param(self) -> None:
        response = self.client.get(
            reverse("key-parliamentary-items-list"), {"ordering": "title"}
        )
        self.assertEqual(200, response.status_code)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        titles = [item["title"] for item in data]
        self.assertEqual(sorted(titles), titles)

    def test_detail_route(self) -> None:
        item_id = ParliamentaryItem.objects.first().id  # type: ignore[union-attr]
        response = self.client.get(
            reverse("key-parliamentary-items-detail", args=[item_id])
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(item_id, response.data["id"])


class TestPCAComponentPartyScoreViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_list_returns_200(self) -> None:
        url = reverse("pcacomponentpartyscore-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(data), PCAComponentPartyScore.objects.all().count()
        )

    def test_filter_by_analysis_id(self) -> None:
        url = reverse("pcacomponentpartyscore-list")
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        response = self.client.get(url, {"analysis": analysis.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            component = PCAComponent.objects.get(id=row["component"])
            self.assertEqual(component.analysis_id, analysis.id)

    def test_filter_by_party_id(self) -> None:
        url = reverse("pcacomponentpartyscore-list")
        party = Party.objects.first()
        assert party is not None
        response = self.client.get(url, {"party": party.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["party"], party.id)

    def test_filter_by_component_number(self) -> None:
        url = reverse("pcacomponentpartyscore-list")
        component = PCAComponent.objects.first()
        assert component is not None
        response = self.client.get(url, {"number": component.number})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            comp = PCAComponent.objects.get(id=row["component"])
            self.assertEqual(comp.number, component.number)

    def test_filter_by_score_gte(self) -> None:
        pcacpc = PCAComponentPartyScore.objects.first()
        assert pcacpc is not None
        url = reverse("pcacomponentpartyscore-list")
        response = self.client.get(url, {"score__gte": pcacpc.score})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertGreaterEqual(row["score"], pcacpc.score)

    def test_filter_by_score_lte(self) -> None:
        pcacpc = PCAComponentPartyScore.objects.first()
        assert pcacpc is not None
        url = reverse("pcacomponentpartyscore-list")
        response = self.client.get(url, {"score__lte": pcacpc.score})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertLessEqual(row["score"], pcacpc.score)

    def test_filter_by_score_exact(self) -> None:
        pcacpc = PCAComponentPartyScore.objects.first()
        assert pcacpc is not None
        url = reverse("pcacomponentpartyscore-list")
        response = self.client.get(url, {"score": pcacpc.score})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["score"], pcacpc.score)

    def test_order_by_score(self) -> None:
        url = reverse("pcacomponentpartyscore-list")
        response = self.client.get(url, {"ordering": "score"})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        scores = [row["score"] for row in data]
        self.assertEqual(scores, sorted(scores))


class TestPCAItemLoadingViewSet(APITestCase):
    def setUp(self) -> None:
        generate_party_votes(
            parliamentary_items=generate_parliamentary_items(10),
            parties=generate_parties(),
        )
        run_pca_analysis(n_components=3)

    def test_list_returns_200(self) -> None:
        url = reverse("pcaitemloading-list")
        response = self.client.get(url)
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        loadings: int = PCAItemLoading.objects.all().count()
        loadings = loadings if loadings <= 100 else 100
        self.assertEqual(len(data), loadings)

    def test_filter_by_analysis_id(self) -> None:
        # Run second analysis to create data that should not be included in the
        # results.
        run_pca_analysis(n_components=3)
        url = reverse("pcaitemloading-list")
        analysis = PCAAnalysis.objects.first()
        assert analysis is not None
        response = self.client.get(url, {"analysis": analysis.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            component = PCAComponent.objects.get(id=row["component"])
            self.assertEqual(component.analysis_id, analysis.id)

    def test_filter_by_parliamentary_item_id(self) -> None:
        url = reverse("pcaitemloading-list")
        item = ParliamentaryItem.objects.first()
        assert item is not None
        response = self.client.get(url, {"parliamentary_item": item.id})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["parliamentary_item"], item.id)

    def test_filter_by_component_number(self) -> None:
        url = reverse("pcaitemloading-list")
        component = PCAComponent.objects.first()
        assert component is not None
        response = self.client.get(url, {"number": component.number})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            comp = PCAComponent.objects.get(id=row["component"])
            self.assertEqual(comp.number, component.number)

    def test_filter_by_loading_gte(self) -> None:
        pcal = PCAItemLoading.objects.first()
        assert pcal is not None
        url = reverse("pcaitemloading-list")
        response = self.client.get(url, {"loading__gte": pcal.loading})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertGreaterEqual(row["loading"], pcal.loading)

    def test_filter_by_loading_lte(self) -> None:
        pcal = PCAItemLoading.objects.first()
        assert pcal is not None
        url = reverse("pcaitemloading-list")
        response = self.client.get(url, {"loading__lte": pcal.loading})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertLessEqual(row["loading"], pcal.loading)

    def test_filter_by_loading_exact(self) -> None:
        pcal = PCAItemLoading.objects.first()
        assert pcal is not None
        url = reverse("pcaitemloading-list")
        response = self.client.get(url, {"loading": pcal.loading})
        data: list[dict[str, Any]] = response.data.get("results", response.data)
        self.assertEqual(response.status_code, 200)
        for row in data:
            self.assertEqual(row["loading"], pcal.loading)


class TestMotionExplorerApi(APITestCase):
    def setUp(self) -> None:
        self.old = ParliamentaryItemFactory(
            title="Motie over stikstof",
            text=["verzoekt de regering de coördinatie te verbeteren"],
            vote_date=date(2026, 1, 5),
            document_id="kst-36848-53",
        )
        self.new = ParliamentaryItemFactory(
            title="Motie over woningbouw",
            text=["constaterende dat er te weinig woningen zijn"],
            vote_date=date(2026, 3, 9),
        )
        self.party = Party.objects.create(
            api_id="p1", name="Partij Een", abbreviation="P1"
        )
        PartyVote.objects.create(
            party=self.party, parliamentary_item=self.old, vote=VoteType.FOR
        )

    def ids(self, params: dict[str, str]) -> list[int]:
        response = self.client.get(reverse("parliamentaryitem-list"), params)
        return [item["id"] for item in response.data["results"]]

    def test_newest_vote_first_by_default(self) -> None:
        self.assertEqual([self.new.id, self.old.id], self.ids({}))

    def test_search_title(self) -> None:
        self.assertEqual([self.old.id], self.ids({"search": "STIKSTOF"}))

    def test_search_text(self) -> None:
        self.assertEqual([self.new.id], self.ids({"search": "woningen zijn"}))

    def test_search_text_with_accents(self) -> None:
        # Stored as JSON, which escapes non-ASCII characters.
        self.assertEqual([self.old.id], self.ids({"search": "coördinatie"}))

    def test_search_combines_with_filters(self) -> None:
        self.assertEqual(
            [],
            self.ids({"search": "stikstof", "vote_date__gte": "2026-02-01"}),
        )

    def test_detail_has_documents_and_votes(self) -> None:
        response = self.client.get(
            reverse("parliamentaryitem-detail", args=[self.old.id])
        )
        data = response.data
        self.assertEqual(
            [
                "https://zoek.officielebekendmakingen.nl/kst-36848-53.html",
                "https://zoek.officielebekendmakingen.nl/kst-36848-53.pdf",
            ],
            [doc["url"] for doc in data["documents"]],
        )
        self.assertEqual(
            [
                {
                    "party": self.party.id,
                    "abbreviation": "P1",
                    "name": "Partij Een",
                    "vote": "For",
                }
            ],
            data["votes"],
        )

    def test_detail_without_document(self) -> None:
        response = self.client.get(
            reverse("parliamentaryitem-detail", args=[self.new.id])
        )
        self.assertEqual([], response.data["documents"])

    def test_list_leaves_out_detail_fields(self) -> None:
        response = self.client.get(reverse("parliamentaryitem-list"))
        for field in ("text", "votes", "documents"):
            self.assertNotIn(field, response.data["results"][0])


class TestStatusSync(APITestCase):
    def test_last_successful_sync(self) -> None:
        ImportRun.objects.create(
            status=ImportRunStatus.SUCCEEDED, finished_at=timezone.now()
        )
        data = self.client.get(reverse("status")).data
        self.assertIsNotNone(data["last_synced_at"])
        self.assertIsNone(data["last_sync_failed_at"])

    def test_failed_latest_sync_is_reported(self) -> None:
        success = ImportRun.objects.create(
            status=ImportRunStatus.SUCCEEDED, finished_at=timezone.now()
        )
        failed = ImportRun.objects.create(
            status=ImportRunStatus.FAILED, finished_at=timezone.now()
        )
        data = self.client.get(reverse("status")).data
        self.assertEqual(success.finished_at, data["last_synced_at"])
        self.assertEqual(failed.finished_at, data["last_sync_failed_at"])

    def test_never_synced(self) -> None:
        data = self.client.get(reverse("status")).data
        self.assertIsNone(data["last_synced_at"])
