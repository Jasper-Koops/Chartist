import copy
import io
from datetime import date
from typing import Any
import requests
from django.test import TestCase
from scraper.dto import BesluitDTO, StemmingDTO
from scraper.tests.factories import PartyFactory
from django.core.management import call_command
from scraper.utils import ParliamentApi, aggregate_party_votes, run_import
from scraper.models import (
    ImportRun,
    ImportRunStatus,
    Party,
    PartyAlias,
    PartyLogo,
    PartySuccession,
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
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


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
        if url.endswith("/resource"):
            return MockedResponse({}, 200, content=PNG)
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
        # Party request + 3 logos + Zaak request + 12 lookups of party ids
        # the votes reference but the party fixture lacks (see
        # _resolve_unknown_parties) + 4 XML downloads.
        self.assertEqual(21, mocked_get.call_count)

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


class TestPartyLogos(TestCase):
    """Logos are downloaded with the parties, only when new or changed."""

    def setUp(self) -> None:
        self.api = ParliamentApi()
        self.parties = copy.deepcopy(PARTY_API_RESPONSE)
        self.ids = [str(party["Id"]) for party in self.parties]
        # ChristenUnie a PNG, SP a JPEG, PvdD fails.
        self.logos: dict[str, MockedResponse] = {
            self.ids[0]: MockedResponse({}, 200, content=PNG),
            self.ids[1]: MockedResponse({}, 200, content=JPEG),
            self.ids[2]: MockedResponse({}, 404),
        }
        self.logo_requests: list[str] = []
        # Earlier registrations with a logo, by abbreviation.
        self.earlier: dict[str, list[dict[str, Any]]] = {}
        self.lookups: list[str] = []

    def side_effect(
        self, url: str, *args: Any, **kwargs: Any
    ) -> MockedResponse:
        if url.endswith("/resource"):
            self.logo_requests.append(url)
            party_id = url.split("(")[1].split(")")[0]
            return self.logos[party_id]
        query = (kwargs.get("params") or {}).get("$filter") or ""
        if "Afkorting eq" in query:
            abbreviation = query.split("'")[1]
            self.lookups.append(abbreviation)
            return MockedResponse(
                {"value": self.earlier.get(abbreviation, [])}, 200
            )
        return MockedResponse({"value": self.parties}, 200)

    def import_parties(self) -> None:
        with mock.patch(
            "scraper.utils.requests.Session.get", side_effect=self.side_effect
        ):
            self.api.import_parties()

    def test_logos_are_stored_with_their_real_type(self) -> None:
        self.import_parties()
        christenunie = Party.objects.get(abbreviation="ChristenUnie")
        sp = Party.objects.get(abbreviation="SP")
        # The API says image/gif and image/png; the bytes decide.
        self.assertEqual("image/png", christenunie.logo.content_type)
        self.assertEqual(PNG, bytes(christenunie.logo.image))
        self.assertEqual("image/jpeg", sp.logo.content_type)
        self.assertEqual(2930, christenunie.logo_length)
        self.assertEqual(
            f"/party/{christenunie.pk}/logo/?v=2930", christenunie.logo_url
        )

    def test_failed_logo_is_skipped(self) -> None:
        self.import_parties()
        pvdd = Party.objects.get(abbreviation="PvdD")
        self.assertIsNone(pvdd.logo_length)
        self.assertIsNone(pvdd.logo_url)
        self.assertFalse(PartyLogo.objects.filter(party=pvdd).exists())

    def test_unrecognised_image_is_skipped(self) -> None:
        self.logos[self.ids[0]] = MockedResponse(
            {}, 200, content=b"<html>Not found</html>"
        )
        self.import_parties()
        self.assertIsNone(
            Party.objects.get(abbreviation="ChristenUnie").logo_length
        )

    def test_unchanged_logo_is_not_downloaded_again(self) -> None:
        self.import_parties()
        self.logo_requests.clear()
        self.import_parties()
        # Only the logo that failed is tried again.
        self.assertEqual(1, len(self.logo_requests))
        self.assertIn(self.ids[2], self.logo_requests[0])

    def test_changed_logo_is_downloaded_again(self) -> None:
        self.import_parties()
        self.parties[1]["ContentLength"] = 4000
        self.logos[self.ids[1]] = MockedResponse({}, 200, content=PNG)
        self.import_parties()
        sp = Party.objects.get(abbreviation="SP")
        self.assertEqual(4000, sp.logo_length)
        self.assertEqual("image/png", sp.logo.content_type)

    def test_logo_of_an_earlier_registration(self) -> None:
        # Registered again without a logo (like 50PLUS in 2025): the logo of
        # its earlier registration under the same abbreviation is used.
        self.parties[0]["ContentLength"] = None
        self.earlier["ChristenUnie"] = [
            {"Id": "earlier-id", "ContentLength": 13605}
        ]
        self.logos["earlier-id"] = MockedResponse({}, 200, content=PNG)
        self.import_parties()
        christenunie = Party.objects.get(abbreviation="ChristenUnie")
        self.assertEqual(13605, christenunie.logo_length)
        self.assertEqual(PNG, bytes(christenunie.logo.image))
        self.assertIn("Fractie(earlier-id)/resource", self.logo_requests[0])

    def test_earlier_logo_is_not_downloaded_again(self) -> None:
        self.parties[0]["ContentLength"] = None
        self.earlier["ChristenUnie"] = [
            {"Id": "earlier-id", "ContentLength": 13605}
        ]
        self.logos["earlier-id"] = MockedResponse({}, 200, content=PNG)
        self.import_parties()
        self.logo_requests.clear()
        self.import_parties()
        self.assertNotIn("earlier-id", "".join(self.logo_requests))

    def test_removed_logo_is_deleted(self) -> None:
        self.import_parties()
        self.parties[0]["ContentLength"] = None
        self.import_parties()
        christenunie = Party.objects.get(abbreviation="ChristenUnie")
        self.assertIsNone(christenunie.logo_length)
        self.assertFalse(PartyLogo.objects.filter(party=christenunie).exists())
        # It looked for an earlier logo, and found none.
        self.assertEqual(["ChristenUnie"], self.lookups)


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

    def test_roll_call_even_split_is_separate_from_absence(self) -> None:
        votes = aggregate_party_votes(
            [
                stemming("a", VoteType.FOR),
                stemming("a", VoteType.AGAINST),
                stemming("a", VoteType.ABSTAIN),
            ]
        )
        self.assertEqual({"a": VoteType.SPLIT}, votes)

    def test_roll_call_all_absent_is_abstain(self) -> None:
        votes = aggregate_party_votes(
            [stemming("a", VoteType.ABSTAIN), stemming("a", VoteType.ABSTAIN)]
        )
        self.assertEqual({"a": VoteType.ABSTAIN}, votes)


class TestImportRollCallVote(TestCase):
    @mock.patch("scraper.utils.requests.Session.get")
    def test_import_preserves_split_separately_from_absence(
        self, mocked_get: mock.Mock
    ) -> None:
        zaak = copy.deepcopy(ZAAK_API_RESPONSE[0])
        split_id, absent_id = [p["Id"] for p in PARTY_API_RESPONSE[:2]]
        zaak["Besluit"][0]["Stemming"] = [
            {"Fractie_Id": split_id, "Soort": "Voor"},
            {"Fractie_Id": split_id, "Soort": "Tegen"},
            {"Fractie_Id": absent_id, "Soort": "Niet deelgenomen"},
        ]
        mocked_get.side_effect = route_responses([zaak])
        api = ParliamentApi()
        api.import_parties()
        api.import_votes()
        self.assertEqual(
            VoteType.SPLIT, PartyVote.objects.get(party__api_id=split_id).vote
        )
        self.assertEqual(
            VoteType.ABSTAIN,
            PartyVote.objects.get(party__api_id=absent_id).vote,
        )

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


def fractie(
    fractie_id: str, abbreviation: str, start: str, end: str | None = None
) -> dict[str, Any]:
    return {
        "Id": fractie_id,
        "Afkorting": abbreviation,
        "DatumActief": f"{start}T00:00:00+02:00",
        "DatumInactief": f"{end}T00:00:00+02:00" if end else None,
    }


def seat(members: list[str], start: str, end: str | None) -> dict[str, Any]:
    return {
        "FractieZetelPersoon": [
            {
                "Persoon_Id": member,
                "Van": f"{start}T00:00:00+02:00",
                "TotEnMet": f"{end}T00:00:00+02:00" if end else None,
            }
            for member in members
        ]
    }


class TestImportSuccessions(TestCase):
    def setUp(self) -> None:
        patcher = mock.patch("scraper.utils.requests.Session.get")
        self.mocked_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.fracties: list[dict[str, Any]] = []
        self.seats: dict[str, list[dict[str, Any]]] = {}
        self.mocked_get.side_effect = self.respond
        self.api = ParliamentApi()

    def respond(self, url: str, *args: Any, **kwargs: Any) -> MockedResponse:
        if url.endswith("FractieZetel"):
            fractie_id = kwargs["params"]["$filter"].split("Fractie_Id eq ")[1]
            return MockedResponse(
                {"value": self.seats.get(fractie_id, [])}, 200
            )
        return MockedResponse({"value": self.fracties}, 200)

    def add(
        self,
        fractie_id: str,
        start: str,
        end: str | None,
        members: list[str],
    ) -> None:
        PartyFactory(api_id=fractie_id)
        self.fracties.append(fractie(fractie_id, fractie_id, start, end))
        self.seats[fractie_id] = [seat(members, start, end)]

    def detect(self) -> list[tuple[str, str]]:
        self.api.import_successions()
        return list(
            PartySuccession.objects.values_list(
                "predecessor__api_id", "successor__api_id"
            )
        )

    def members(self, n: int, prefix: str = "m") -> list[str]:
        return [f"{prefix}{i}" for i in range(n)]

    def test_rename_is_detected(self) -> None:
        # GroenLinks-PvdA -> PRO: 19 of 20 members continue.
        self.add("gl", "2023-10-27", "2026-06-10", self.members(20))
        self.add("pro", "2026-06-09", None, self.members(19) + ["newcomer"])
        self.assertEqual([("gl", "pro")], self.detect())
        succession = PartySuccession.objects.get()
        self.assertEqual(date(2026, 6, 9), succession.date)
        self.assertAlmostEqual(0.95, succession.member_overlap)

    def test_split_is_not_a_succession(self) -> None:
        # PVV -> Groep Markuszower: the original party continues.
        self.add("pvv", "2006-11-30", None, self.members(26))
        self.add("mk", "2026-01-20", None, self.members(7))
        self.assertEqual([], self.detect())

    def test_split_off_from_ended_party_is_not_a_succession(self) -> None:
        # Only part of the members continue in the new party.
        self.add("old", "2023-10-27", "2026-06-10", self.members(20))
        self.add("new", "2026-06-09", None, self.members(10))
        self.assertEqual([], self.detect())

    def test_merger_is_not_a_succession(self) -> None:
        self.add("a", "2023-10-27", "2026-06-10", self.members(10, "a"))
        self.add("b", "2023-10-27", "2026-06-10", self.members(10, "b"))
        self.add(
            "ab",
            "2026-06-09",
            None,
            self.members(10, "a") + self.members(10, "b"),
        )
        self.assertEqual([], self.detect())

    def test_large_gap_is_not_a_succession(self) -> None:
        self.add("old", "2023-10-27", "2026-03-01", self.members(20))
        self.add("new", "2026-06-09", None, self.members(20))
        self.assertEqual([], self.detect())

    def test_unknown_parties_are_ignored(self) -> None:
        self.add("gl", "2023-10-27", "2026-06-10", self.members(20))
        self.fracties.append(fractie("pro", "pro", "2026-06-09"))
        self.seats["pro"] = [seat(self.members(20), "2026-06-09", None)]
        self.assertEqual([], self.detect())


class TestRunImport(TestCase):
    def setUp(self) -> None:
        patcher = mock.patch("scraper.utils.requests.Session.get")
        self.mocked_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.zaken = copy.deepcopy(ZAAK_API_RESPONSE)
        self.mocked_get.side_effect = route_responses(self.zaken)

    def test_successful_run_is_recorded_with_counts(self) -> None:
        messages: list[str] = []
        result = run_import(ParliamentApi(), announce=messages.append)

        run = ImportRun.objects.get()
        self.assertEqual(ImportRunStatus.SUCCEEDED, run.status)
        self.assertIsNotNone(run.finished_at)
        self.assertEqual(result.created, run.created)
        self.assertEqual(result.votes_created, run.votes_created)
        self.assertEqual(4, run.created)
        self.assertEqual(
            ["Importing party data", "Importing vote data"], messages
        )

    def test_failed_run_is_recorded_and_raised(self) -> None:
        self.mocked_get.side_effect = requests.exceptions.ConnectionError(
            "down"
        )
        with self.assertRaises(requests.exceptions.ConnectionError):
            run_import(ParliamentApi())

        run = ImportRun.objects.get()
        self.assertEqual(ImportRunStatus.FAILED, run.status)
        self.assertIn("ConnectionError", run.error)
        self.assertIsNotNone(run.finished_at)

    def test_import_command_records_a_run(self) -> None:
        call_command("import_data", stdout=io.StringIO())
        self.assertEqual(
            ImportRunStatus.SUCCEEDED, ImportRun.objects.get().status
        )

    def test_document_id_is_stored(self) -> None:
        run_import(ParliamentApi())
        item = ParliamentaryItem.objects.get(api_id=ZAAK_API_RESPONSE[0]["Id"])
        self.assertEqual("kst-99999-0", item.document_id)

    def test_unchanged_document_text_is_not_downloaded_again(self) -> None:
        run_import(ParliamentApi())
        result = run_import(ParliamentApi())
        self.assertEqual(0, result.texts_fetched)

    def test_changed_publication_is_downloaded(self) -> None:
        run_import(ParliamentApi())
        version = self.zaken[0]["Document"][0]["HuidigeDocumentVersie"]
        version["ExterneIdentifier"] = "kst-99999-replacement"
        result = run_import(ParliamentApi())
        item = ParliamentaryItem.objects.get(api_id=self.zaken[0]["Id"])
        self.assertEqual(1, result.texts_fetched)
        self.assertEqual(
            "kst-99999-replacement", item.text_source["document_id"]
        )

    def test_changed_version_with_same_publication_is_downloaded(self) -> None:
        version = self.zaken[0]["Document"][0]["HuidigeDocumentVersie"]
        version["Id"] = "first-version"
        run_import(ParliamentApi())
        version["Id"] = "second-version"
        result = run_import(ParliamentApi())
        item = ParliamentaryItem.objects.get(api_id=self.zaken[0]["Id"])
        self.assertEqual(1, result.texts_fetched)
        self.assertEqual("second-version", item.text_source["version_id"])

    def test_modified_version_is_downloaded(self) -> None:
        version = self.zaken[0]["Document"][0]["HuidigeDocumentVersie"]
        version["GewijzigdOp"] = "2026-01-01T12:00:00Z"
        run_import(ParliamentApi())
        version["GewijzigdOp"] = "2026-02-01T12:00:00Z"
        result = run_import(ParliamentApi())
        self.assertEqual(1, result.texts_fetched)

    def test_failed_refresh_keeps_source_and_retries_next_import(self) -> None:
        version = self.zaken[0]["Document"][0]["HuidigeDocumentVersie"]
        version["Id"] = "first-version"
        run_import(ParliamentApi())
        item = ParliamentaryItem.objects.get(api_id=self.zaken[0]["Id"])
        old_text = item.text
        version["Id"] = "second-version"
        url = (
            "https://zoek.officielebekendmakingen.nl/"
            f"{version['ExterneIdentifier']}.xml"
        )
        self.mocked_get.side_effect = route_responses(
            self.zaken, {url: requests.exceptions.ConnectionError("down")}
        )
        result = run_import(ParliamentApi())
        item.refresh_from_db()
        self.assertEqual(1, result.texts_failed)
        self.assertEqual(old_text, item.text)
        self.assertEqual("first-version", item.text_source["version_id"])
        self.mocked_get.side_effect = route_responses(self.zaken)
        result = run_import(ParliamentApi())
        item.refresh_from_db()
        self.assertEqual(1, result.texts_fetched)
        self.assertEqual("second-version", item.text_source["version_id"])


OLD_ID = "old-50plus"
NEW_ID = "new-50plus"


def fractie_record(
    fractie_id: str, abbreviation: str = "50PLUS", inactive: bool = False
) -> dict[str, Any]:
    return {
        "Id": fractie_id,
        "NaamNL": "50PLUS",
        "Afkorting": abbreviation,
        "AantalZetels": 0 if inactive else 2,
        "AantalStemmen": 0,
        "DatumActief": "2012-09-20T00:00:00+02:00",
        "DatumInactief": "2021-05-11T00:00:00+02:00" if inactive else None,
    }


class TestPartyAliases(TestCase):
    """
    A party registered again under a new id while the API still records its
    votes under the old, inactive id (as for 50PLUS).
    """

    def setUp(self) -> None:
        patcher = mock.patch("scraper.utils.requests.Session.get")
        self.mocked_get = patcher.start()
        self.addCleanup(patcher.stop)
        self.records = {
            NEW_ID: fractie_record(NEW_ID),
            OLD_ID: fractie_record(OLD_ID, inactive=True),
        }
        zaak = copy.deepcopy(ZAAK_API_RESPONSE[0])
        zaak["Besluit"][0]["Stemming"] = [
            {"Fractie_Id": OLD_ID, "Soort": "Voor"}
        ]
        self.zaken = [zaak]
        self.mocked_get.side_effect = self.respond
        self.api = ParliamentApi()

    def respond(self, url: str, *args: Any, **kwargs: Any) -> MockedResponse:
        params = kwargs.get("params") or {}
        if url.endswith("Fractie"):
            id_filter = params.get("$filter", "")
            if "Id eq " in id_filter:
                fractie_id = id_filter.split("Id eq ")[1]
                record = self.records.get(fractie_id)
                return MockedResponse(
                    {"value": [record] if record else []}, 200
                )
            return MockedResponse({"value": [self.records[NEW_ID]]}, 200)
        if MOTION_XML_HOST in url:
            return MockedResponse({}, 200, content=SIMPLE_XML)
        return MockedResponse({"value": self.zaken}, 200)

    def run_import(self) -> None:
        self.api.import_parties()
        self.api.import_votes()

    def test_existing_party_takes_new_id_and_keeps_old_as_alias(self) -> None:
        party = PartyFactory(
            api_id=OLD_ID, abbreviation="50PLUS", name="50PLUS"
        )
        self.run_import()

        party.refresh_from_db()
        self.assertEqual(NEW_ID, party.api_id)
        self.assertEqual(
            [OLD_ID], list(party.aliases.values_list("api_id", flat=True))
        )
        self.assertEqual(1, Party.objects.filter(abbreviation="50PLUS").count())
        # Votes under the old id link to the party.
        self.assertEqual(1, PartyVote.objects.filter(party=party).count())

    def test_fresh_database_finds_alias_from_votes(self) -> None:
        self.run_import()
        party = Party.objects.get(abbreviation="50PLUS")
        self.assertEqual(NEW_ID, party.api_id)
        self.assertTrue(
            PartyAlias.objects.filter(api_id=OLD_ID, party=party).exists()
        )
        self.assertEqual(1, PartyVote.objects.filter(party=party).count())

    def test_unknown_id_of_another_party_is_not_an_alias(self) -> None:
        self.records[OLD_ID] = fractie_record(
            OLD_ID, abbreviation="XYZ", inactive=True
        )
        self.run_import()
        self.assertFalse(PartyAlias.objects.exists())
        self.assertFalse(PartyVote.objects.exists())

    def test_active_record_with_same_abbreviation_is_not_an_alias(self) -> None:
        self.records[OLD_ID] = fractie_record(OLD_ID, inactive=False)
        self.run_import()
        self.assertFalse(PartyAlias.objects.exists())

    def test_votes_under_both_ids_give_one_party_vote(self) -> None:
        PartyFactory(api_id=OLD_ID, abbreviation="50PLUS", name="50PLUS")
        self.zaken[0]["Besluit"][0]["Stemming"] = [
            {"Fractie_Id": OLD_ID, "Soort": "Voor"},
            {"Fractie_Id": NEW_ID, "Soort": "Voor"},
        ]
        self.run_import()
        party = Party.objects.get(abbreviation="50PLUS")
        vote = PartyVote.objects.get(party=party)
        self.assertEqual(VoteType.FOR, vote.vote)

    def test_failing_party_does_not_roll_back_others(self) -> None:
        # "second" clashes with "first" on the unique name: a database error
        # in the middle of the import must not undo the other parties.
        first = fractie_record("first", abbreviation="AAA")
        second = fractie_record("second", abbreviation="BBB")
        third = fractie_record("third", abbreviation="CCC")
        third["NaamNL"] = "Another party"
        self.mocked_get.side_effect = lambda url, *a, **k: MockedResponse(
            {"value": [first, second, third]}, 200
        )
        self.api.import_parties()
        self.assertEqual(
            {"first", "third"},
            set(Party.objects.values_list("api_id", flat=True)),
        )
