from typing import Any, Mapping
from django.test import TestCase
from scraper.dto import (
    AgendapuntZaakBesluitVolgordeDTO,
    StemmingDTO,
    ZaakDTO,
)
from scraper.models import ParliamentaryItemStatusTypes
from scraper.tests.factories import AgendapuntZaakBesluitVolgordeDTOFactory
from scraper.tests.fixtures.utils_fixtures import BESLUIT_API_RESPONSE


class TestStemmingDTO(TestCase):
    def test_dto_from_api_valid_data(self) -> None:
        data: Mapping[str, Any] = BESLUIT_API_RESPONSE[1]["Stemming"][0]
        stemming_dto: StemmingDTO = StemmingDTO.from_api(data)
        self.assertEqual("For", stemming_dto.Soort)
        self.assertEqual(
            "d3b4d880-ef37-4ce6-99ec-4940266ac466", stemming_dto.Fractie_Id
        )

    def test_get_party_vote_type_for(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("Voor")
        self.assertEqual(vote_type.value, "For")

    def test_get_party_vote_type_against(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("Tegen")
        self.assertEqual(vote_type.value, "Against")

    def test_get_party_vote_type_abstain(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("niet deelgenomen")
        self.assertEqual(vote_type.value, "Abstain")

    def test_get_party_vote_type_unknown(self) -> None:
        with self.assertRaisesMessage(ValueError, "Unknown vote type: FLUPS"):
            StemmingDTO.get_party_vote_type("FLUPS")

    def test_get_party_vote_type_with_period(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("voor.")
        self.assertEqual(vote_type.value, "For")

    def test_get_party_vote_type_with_whitespace(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("  tegen  ")
        self.assertEqual(vote_type.value, "Against")

    def test_get_party_vote_type_case_insensitive(self) -> None:
        vote_type = StemmingDTO.get_party_vote_type("nIeT dEeLgEnOmEn")
        self.assertEqual(vote_type.value, "Abstain")


class TestZaakDTO(TestCase):
    def test_dto_from_api_valid_data(self) -> None:
        data: dict[str, Any] = BESLUIT_API_RESPONSE[1]["Zaak"][0]
        zaak_dto: ZaakDTO = ZaakDTO.from_api(data)
        self.assertEqual("669e6b7e-2f11-4ef6-99bd-336e25711dbf", zaak_dto.Id)
        self.assertEqual("Motie", zaak_dto.Soort)
        self.assertEqual("Europese Raad", zaak_dto.Titel)
        self.assertEqual(
            "Motie van de leden Bikker en Erkens over zich in Europa "
            "inzetten voor het verbeteren van informatiedeling en "
            "beleidsafstemming om de dreiging van jihadisme te verminderen",
            zaak_dto.Onderwerp,
        )
        self.assertEqual("2025-2026", zaak_dto.Vergaderjaar)
        self.assertEqual(
            "2024-12-16T00:00:00+01:00", zaak_dto.GestartOp.isoformat()
        )
        self.assertEqual(
            "2024-12-17T13:18:36.050000+01:00", zaak_dto.GewijzigdOp.isoformat()
        )


class TestAgendapuntZaakBesluitVolgordeDTO(TestCase):
    def test_factory_init(self) -> None:
        dto = AgendapuntZaakBesluitVolgordeDTOFactory()
        self.assertIsInstance(dto, AgendapuntZaakBesluitVolgordeDTO)

    def test_dto_from_api_valid_data(self) -> None:
        data: dict[str, Any] = BESLUIT_API_RESPONSE[1]
        azb_dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTO.from_api(data)
        )
        self.assertEqual("59b3219e-d798-4b15-a7b9-0066221f82db", azb_dto.Id)
        self.assertEqual(
            "c94577ba-e5e2-422c-9486-da8e69369609", azb_dto.Agendapunt_Id
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED, azb_dto.BesluitSoort
        )
        self.assertEqual(
            "2025-12-17T13:18:36.047000+01:00", azb_dto.GewijzigdOp.isoformat()
        )
        zaak_dto = ZaakDTO.from_api(data["Zaak"][0])
        self.assertEqual(zaak_dto, azb_dto.Zaak[0])
        stemming_dto = StemmingDTO.from_api(data["Stemming"][0])
        self.assertEqual(stemming_dto, azb_dto.Stemming[0])

    def test_get_parliamentary_item_status_unknown(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        with self.assertRaisesMessage(
            ValueError, "Unknown parliamentary item status: Accepted"
        ):
            dto.get_parliamentary_item_status("Accepted")

    def test_get_parliamentary_item_status_aangenomen(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status("aangenomen"),
        )

    def test_get_parliamentary_item_status_verworpen(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.REJECTED,
            dto.get_parliamentary_item_status("verworpen"),
        )

    def test_get_parliamentary_item_status_aangehouden(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.PENDING,
            dto.get_parliamentary_item_status("aangehouden"),
        )

    def test_get_parliamentary_item_status_with_period(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status("aangenomen."),
        )

    def test_get_parliamentary_item_status_with_whitespace(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status(" aangenomen "),
        )

    def test_get_parliamentary_item_status_case_instensitive(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status("aAnGeNOmeN"),
        )

    def test_get_parliamentary_item_status_votes_in_value(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status("Aangenomen (77-73)."),
        )

    def test_get_parliamentary_item_other_expected_diversions(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        self.assertEqual(
            ParliamentaryItemStatusTypes.ACCEPTED,
            dto.get_parliamentary_item_status("Stemming: Aangenomen."),
        )

    def test_negation_detected(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        with self.assertRaisesMessage(
            ValueError, "Negation detected in: niet Aangenomen"
        ):
            dto.get_parliamentary_item_status("niet Aangenomen")

    def test_case_insensitive_negation_detection(self) -> None:
        dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTOFactory()
        )
        with self.assertRaisesMessage(
            ValueError, "Negation detected in:  NiEt. Aangenomen"
        ):
            dto.get_parliamentary_item_status(" NiEt. Aangenomen")
