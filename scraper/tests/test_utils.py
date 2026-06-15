import copy
from typing import Any
from django.test import TestCase
from scraper.utils import ParliamentApi
from scraper.models import Party, PartyVote, ParliamentaryItem
from unittest import mock
from scraper.tests.fixtures.utils_fixtures import (
    PARTY_API_RESPONSE,
    ZAAK_API_RESPONSE,
)

SIMPLE_XML = b"<root><al>Constaterende dat dit een test is.</al></root>"


class MockedResponse:
    def __init__(
        self, json_data: dict[str, Any], status_code: int, content: bytes = b""
    ) -> None:
        self.json_data: dict[str, Any] = json_data
        self.status_code: int = status_code
        self.content: bytes = content
        self.ok: bool = status_code < 400

    def json(self) -> dict[str, Any]:
        return self.json_data

    def raise_for_status(self) -> int:
        return self.status_code


class TestParliamentApi(TestCase):
    def setUp(self) -> None:
        self.api = ParliamentApi()

    @mock.patch("scraper.utils.requests.get")
    def test_party_import(self, mocked_get: mock.Mock) -> None:
        mocked_get.return_value = MockedResponse(
            {"value": PARTY_API_RESPONSE}, 200
        )
        self.assertEqual(0, Party.objects.count())
        self.api.import_parties()
        self.assertEqual(3, Party.objects.count())

        pvdd: Party = Party.objects.get(abbreviation="PvdD")
        self.assertEqual(PARTY_API_RESPONSE[2]["NaamNL"], pvdd.name)
        self.api.import_votes()

    @mock.patch("scraper.utils.requests.get")
    def test_import_votes(self, mocked_get: mock.Mock) -> None:
        xml_response = MockedResponse({}, 200, content=SIMPLE_XML)
        mocked_get.side_effect = [
            MockedResponse({"value": PARTY_API_RESPONSE}, 200),
            MockedResponse({"value": ZAAK_API_RESPONSE}, 200),
            # Part 2: XML fetch for each of the 4 newly created items
            xml_response,
            xml_response,
            xml_response,
            xml_response,
        ]
        self.api.import_parties()
        self.api.import_votes()
        self.assertEqual(4, ParliamentaryItem.objects.count())
        self.assertEqual(12, PartyVote.objects.count())

    @mock.patch("scraper.utils.requests.get")
    def test_import_votes_skips_bad_item(self, mocked_get: mock.Mock) -> None:
        # Build a response where the first item has an unrecognised BesluitSoort
        bad_item = copy.deepcopy(ZAAK_API_RESPONSE[0])
        bad_item["Besluit"][0]["BesluitSoort"] = "Ingetrokken"
        bad_response = [bad_item] + ZAAK_API_RESPONSE[1:]

        xml_response = MockedResponse({}, 200, content=SIMPLE_XML)
        mocked_get.side_effect = [
            MockedResponse({"value": PARTY_API_RESPONSE}, 200),
            MockedResponse({"value": bad_response}, 200),
            # XML fetch only for the 3 successfully processed items
            xml_response,
            xml_response,
            xml_response,
        ]
        self.api.import_parties()
        self.api.import_votes()
        self.assertEqual(3, ParliamentaryItem.objects.count())
        self.assertEqual(9, PartyVote.objects.count())
