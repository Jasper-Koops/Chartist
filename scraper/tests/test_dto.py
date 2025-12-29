from django.test import TestCase
from scraper.dto import AgendapuntZaakBesluitVolgordeDTO
from scraper.tests.factories import AgendapuntZaakBesluitVolgordeDTOFactory


class TestAgendapuntZaakBesluitVolgordeDTO(TestCase):
    def test_factory_init(self) -> None:
        dto = AgendapuntZaakBesluitVolgordeDTOFactory()
        self.assertIsInstance(dto, AgendapuntZaakBesluitVolgordeDTO)
