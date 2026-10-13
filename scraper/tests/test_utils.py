import copy
from datetime import date
from typing import Any
import requests
from django.test import TestCase
from scraper.dto import BesluitDTO, StemmingDTO
from scraper.utils import ParliamentApi, aggregate_party_votes
from scraper.models import (
    Party,
    PartyVote,
    ParliamentaryItem,
    ParliamentaryItemStatusTypes,
    VoteType,
)
from unittest import mock
from scraper.tests.fixtures.utils_fixtures import (
    PARTY_API_RESPONSE,
    ZAAK_API_RESPONSE,
)

SIMPLE_XML = (
    b"<root><al>De Kamer,</al><al>gehoord de beraadslaging,</al>"
    b"<al>Constaterende dat dit een test is.</al>"
    b"<al>en gaat over tot de orde van de dag.</al></root>"
)
MOTION_XML_HOST = "zoek.officielebekendmakingen.nl"


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

    def raise_for_status(self) -> None:
        if not self.ok:
            raise requests.exceptions.HTTPError(f"{self.status_code} Error")


def route_responses(
    zaak_response: list[dict[str, Any]],
    xml_responses: dict[str, MockedResponse | Exception] | None = None,
) -> Any:
    """
    Build a side_effect that answers by URL, so parallel XML downloads do not
    depend on call order. XML documents default to SIMPLE_XML.
    """
    xml_responses = xml_responses or {}

    def side_effect(url: str, *args: Any, **kwargs: Any) -> MockedResponse:
        if MOTION_XML_HOST in url:
            response = xml_responses.get(
                url, MockedResponse({}, 200, content=SIMPLE_XML)
            )
            if isinstance(response, Exception):
                raise response
            return response
        if url.endswith("Fractie"):
            return MockedResponse({"value": PARTY_API_RESPONSE}, 200)
        return MockedResponse({"value": zaak_response}, 200)

    return side_effect


class TestParliamentApi(TestCase):
    def setUp(self) -> None:
        self.api = ParliamentApi()

    @mock.patch("scraper.utils.requests.Session.get")
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

    @mock.patch("scraper.utils.requests.Session.get")
    def test_import_votes(self, mocked_get: mock.Mock) -> None:
        mocked_get.side_effect = route_responses(ZAAK_API_RESPONSE)
        self.api.import_parties()
        result = self.api.import_votes()
        self.assertEqual(4, ParliamentaryItem.objects.count())
        self.assertEqual(12, PartyVote.objects.count())
        self.assertEqual(4, result.created)
        self.assertEqual(4, result.texts_fetched)
        self.assertEqual(0, result.texts_failed)
        # Party + Zaak request + 4 XML downloads
        self.assertEqual(6, mocked_get.call_count)

    @mock.patch("scraper.utils.requests.Session.get")
    def test_import_votes_skips_bad_item(self, mocked_get: mock.Mock) -> None:
        # Build a response where the first item has an unrecognised BesluitSoort
        bad_item = copy.deepcopy(ZAAK_API_RESPONSE[0])
        bad_item["Besluit"][0]["BesluitSoort"] = "Ingetrokken"
        bad_response = [bad_item] + ZAAK_API_RESPONSE[1:]

        mocked_get.side_effect = route_responses(bad_response)
        self.api.import_parties()
        result = self.api.import_votes()
        self.assertEqual(3, ParliamentaryItem.objects.count())
        self.assertEqual(9, PartyVote.objects.count())
        # XML fetch only for the 3 successfully processed items
        self.assertEqual(3, result.texts_fetched)

    @mock.patch("scraper.utils.requests.Session.get")
    def test_failed_text_download_does_not_abort_import(
        self, mocked_get: mock.Mock
    ) -> None:
        failing_url = mocked_xml_url(ZAAK_API_RESPONSE[0])
        mocked_get.side_effect = route_responses(
            ZAAK_API_RESPONSE,
            {failing_url: requests.exceptions.ReadTimeout("timed out")},
        )
        self.api.import_parties()
        result = self.api.import_votes()

        self.assertEqual(4, ParliamentaryItem.objects.count())
        self.assertEqual(3, result.texts_fetched)
        self.assertEqual(1, result.texts_failed)
        failed = ParliamentaryItem.objects.get(
            api_id=ZAAK_API_RESPONSE[0]["Id"]
        )
        self.assertIsNone(failed.text)

    @mock.patch("scraper.utils.requests.Session.get")
    def test_failed_text_is_retried_next_run(
        self, mocked_get: mock.Mock
    ) -> None:
        failing_url = mocked_xml_url(ZAAK_API_RESPONSE[0])
        mocked_get.side_effect = route_responses(
            ZAAK_API_RESPONSE, {failing_url: MockedResponse({}, 404)}
        )
        self.api.import_parties()
        self.api.import_votes()

        mocked_get.side_effect = route_responses(ZAAK_API_RESPONSE)
        result = self.api.import_votes()
        self.assertEqual(0, result.created)
        self.assertEqual(1, result.texts_fetched)

    @mock.patch("scraper.utils.requests.Session.get")
    def test_refetch_texts(self, mocked_get: mock.Mock) -> None:
        mocked_get.side_effect = route_responses(ZAAK_API_RESPONSE)
        self.api.import_parties()
        self.api.import_votes()

        self.assertEqual(0, self.api.import_votes().texts_fetched)
        self.assertEqual(
            4, self.api.import_votes(refetch_texts=True).texts_fetched
        )

    @mock.patch("scraper.utils.requests.Session.get")
    def test_progress_reported(self, mocked_get: mock.Mock) -> None:
        mocked_get.side_effect = route_responses(ZAAK_API_RESPONSE)
        progress = mock.Mock()
        api = ParliamentApi(progress=progress)
        api.import_parties()
        api.import_votes()

        final = {
            call.args[0]: call.args[1:] for call in progress.call_args_list
        }
        self.assertEqual((4, 4), final["Fetching motions"])
        self.assertEqual((4, 4), final["Syncing votes"])
        self.assertEqual((4, 4), final["Fetching motion texts"])


def mocked_xml_url(zaak: dict[str, Any]) -> str:
    externe_id = zaak["Document"][0]["HuidigeDocumentVersie"][
        "ExterneIdentifier"
    ]
    return f"https://{MOTION_XML_HOST}/{externe_id}.xml"


def stemming(fractie_id: str, vote: VoteType) -> StemmingDTO:
    return StemmingDTO(Soort=vote, Fractie_Id=fractie_id)


class TestAggregatePartyVotes(TestCase):
    def test_show_of_hands_one_record_per_party(self) -> None:
        votes = aggregate_party_votes(
            [
                stemming("a", VoteType.FOR),
                stemming("b", VoteType.AGAINST),
                stemming("c", VoteType.ABSTAIN),
            ]
        )
        self.assertEqual(
            {"a": VoteType.FOR, "b": VoteType.AGAINST, "c": VoteType.ABSTAIN},
            votes,
        )

    def test_roll_call_absent_member_does_not_override_party(self) -> None:
        # Order matters for a naive "last record wins" implementation.
        votes = aggregate_party_votes(
            [
                stemming("a", VoteType.AGAINST),
                stemming("a", VoteType.AGAINST),
                stemming("a", VoteType.ABSTAIN),
            ]
        )
        self.assertEqual({"a": VoteType.AGAINST}, votes)

    def test_roll_call_majority_wins_split_party(self) -> None:
        votes = aggregate_party_votes(
            [stemming("a", VoteType.FOR)] * 5
            + [stemming("a", VoteType.AGAINST)] * 4
        )
        self.assertEqual({"a": VoteType.FOR}, votes)

    def test_roll_call_even_split_is_abstain(self) -> None:
        votes = aggregate_party_votes(
            [stemming("a", VoteType.FOR), stemming("a", VoteType.AGAINST)]
        )
        self.assertEqual({"a": VoteType.ABSTAIN}, votes)

    def test_roll_call_all_absent_is_abstain(self) -> None:
        votes = aggregate_party_votes(
            [stemming("a", VoteType.ABSTAIN), stemming("a", VoteType.ABSTAIN)]
        )
        self.assertEqual({"a": VoteType.ABSTAIN}, votes)


class TestImportRollCallVote(TestCase):
    @mock.patch("scraper.utils.requests.Session.get")
    def test_roll_call_stores_one_majority_vote_per_party(
        self, mocked_get: mock.Mock
    ) -> None:
        zaak = copy.deepcopy(ZAAK_API_RESPONSE[0])
        party_id = PARTY_API_RESPONSE[0]["Id"]
        member = {"Fractie_Id": party_id}
        zaak["Besluit"][0]["Stemming"] = [
            {**member, "Soort": "Tegen"},
            {**member, "Soort": "Tegen"},
            {**member, "Soort": "Niet deelgenomen"},
        ]
        mocked_get.side_effect = route_responses([zaak])
        api = ParliamentApi()
        api.import_parties()
        api.import_votes()

        votes = PartyVote.objects.filter(party__api_id=party_id)
        self.assertEqual(1, votes.count())
        self.assertEqual(VoteType.AGAINST, votes.get().vote)


class TestVoteSync(TestCase):
    """Votes are synced with the API on every run, not only on creation."""

    def setUp(self) -> None:
        self.api = ParliamentApi()
        patcher = mock.patch("scraper.utils.requests.Session.get")
        self.mocked_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.zaken = copy.deepcopy(ZAAK_API_RESPONSE)
        self.run_import(self.zaken)
        self.zaak = self.zaken[0]
        self.item = ParliamentaryItem.objects.get(api_id=self.zaak["Id"])

    def run_import(self, zaken: list[dict[str, Any]]) -> Any:
        self.mocked_get.side_effect = route_responses(zaken)
        self.api.import_parties()
        return self.api.import_votes()

    def stemmingen(self) -> list[dict[str, Any]]:
        stemmingen: list[dict[str, Any]] = self.zaak["Besluit"][0]["Stemming"]
        return stemmingen

    def known_stemming(self) -> dict[str, Any]:
        """A vote of a party that exists; votes of unknown parties are
        skipped by the import."""
        known = {party["Id"] for party in PARTY_API_RESPONSE}
        return next(s for s in self.stemmingen() if s["Fractie_Id"] in known)

    def test_unchanged_run_writes_nothing(self) -> None:
        result = self.run_import(self.zaken)
        self.assertEqual(0, result.created)
        self.assertEqual(
            (0, 0, 0, 0),
            (
                result.votes_created,
                result.votes_updated,
                result.votes_deleted,
                result.stale,
            ),
        )
        self.assertFalse(result.has_vote_changes)

    def test_changed_vote_is_updated(self) -> None:
        stemming = self.known_stemming()
        stemming["Soort"] = "Voor" if stemming["Soort"] == "Tegen" else "Tegen"
        result = self.run_import(self.zaken)

        self.assertEqual(1, result.votes_updated)
        self.assertTrue(result.has_vote_changes)
        vote = PartyVote.objects.get(
            parliamentary_item=self.item,
            party__api_id=stemming["Fractie_Id"],
        )
        self.assertEqual(
            StemmingDTO.get_party_vote_type(stemming["Soort"]), vote.vote
        )

    def test_removed_vote_is_deleted(self) -> None:
        removed = self.known_stemming()
        self.stemmingen().remove(removed)
        result = self.run_import(self.zaken)

        self.assertEqual(1, result.votes_deleted)
        self.assertFalse(
            PartyVote.objects.filter(
                parliamentary_item=self.item,
                party__api_id=removed["Fractie_Id"],
            ).exists()
        )

    def test_missing_vote_is_added(self) -> None:
        missing = self.known_stemming()
        PartyVote.objects.filter(
            parliamentary_item=self.item, party__api_id=missing["Fractie_Id"]
        ).delete()
        result = self.run_import(self.zaken)

        self.assertEqual(1, result.votes_created)
        self.assertTrue(
            PartyVote.objects.filter(
                parliamentary_item=self.item,
                party__api_id=missing["Fractie_Id"],
            ).exists()
        )

    def test_item_without_vote_anymore_is_reset(self) -> None:
        votes_before = PartyVote.objects.count()
        item_votes = self.item.partyvote_set.count()
        result = self.run_import(self.zaken[1:])

        self.assertEqual(1, result.stale)
        self.assertEqual(item_votes, result.votes_deleted)
        self.item.refresh_from_db()
        self.assertEqual(ParliamentaryItemStatusTypes.PENDING, self.item.status)
        self.assertEqual(0, self.item.partyvote_set.count())
        self.assertEqual(votes_before - item_votes, PartyVote.objects.count())
        # Already reset items are not reported again.
        self.assertEqual(0, self.run_import(self.zaken[1:]).stale)

    def test_empty_download_does_not_wipe_votes(self) -> None:
        votes_before = PartyVote.objects.count()
        result = self.run_import([])
        self.assertEqual(0, result.stale)
        self.assertEqual(votes_before, PartyVote.objects.count())

    def test_invalid_record_leaves_item_untouched(self) -> None:
        item_votes = self.item.partyvote_set.count()
        self.zaak["Besluit"][0]["BesluitSoort"] = "Onbekend"
        result = self.run_import(self.zaken)

        self.assertEqual(0, result.stale)
        self.assertEqual(item_votes, self.item.partyvote_set.count())

    def test_mistake_votes_are_requested(self) -> None:
        self.run_import(self.zaken)
        zaak_calls = [
            call
            for call in self.mocked_get.call_args_list
            if call.args[0].endswith("Zaak")
        ]
        expand = zaak_calls[-1].kwargs["params"]["$expand"]
        self.assertIn("Stemming(", expand)
        self.assertNotIn("Vergissing", expand)


class TestVoteDate(TestCase):
    def test_vote_date_from_session_uses_local_date(self) -> None:
        agendapunt = {"Activiteit": {"Datum": "2026-04-21T00:30:00+02:00"}}
        # 00:30 local is still 22:30 UTC the day before.
        self.assertEqual(
            date(2026, 4, 21), BesluitDTO.get_vote_date(agendapunt)
        )

    def test_missing_session_gives_none(self) -> None:
        self.assertIsNone(BesluitDTO.get_vote_date(None))
        self.assertIsNone(BesluitDTO.get_vote_date({"Activiteit": None}))
        self.assertIsNone(
            BesluitDTO.get_vote_date({"Activiteit": {"Datum": None}})
        )

    @mock.patch("scraper.utils.requests.Session.get")
    def test_import_stores_vote_date(self, mocked_get: mock.Mock) -> None:
        zaak = copy.deepcopy(ZAAK_API_RESPONSE[0])
        zaak["Besluit"][0]["Agendapunt"] = {
            "Id": "agendapunt",
            "Activiteit": {"Datum": "2026-04-21T15:00:00+02:00"},
        }
        mocked_get.side_effect = route_responses([zaak])
        api = ParliamentApi()
        api.import_parties()
        api.import_votes()

        item = ParliamentaryItem.objects.get(api_id=zaak["Id"])
        self.assertEqual(date(2026, 4, 21), item.vote_date)
