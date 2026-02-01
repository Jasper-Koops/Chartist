from typing import Any
from django.test import TestCase
from scraper.utils import ParliamentApi
from scraper.models import Party, PartyVote, ParliamentaryItem
from unittest import mock
from scraper.tests.fixtures.utils_fixtures import (
    PARTY_API_RESPONSE,
    BESLUIT_API_RESPONSE,
)


class MockedResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int) -> None:
        self.json_data: dict[str, Any] = json_data
        self.status_code: int = status_code

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
        mocked_get.side_effect = [
            MockedResponse({"value": PARTY_API_RESPONSE}, 200),
            MockedResponse({"value": BESLUIT_API_RESPONSE}, 200),
        ]
        self.api.import_parties()
        self.api.import_votes()
        self.assertEqual(4, ParliamentaryItem.objects.count())
        self.assertEqual(12, PartyVote.objects.count())
