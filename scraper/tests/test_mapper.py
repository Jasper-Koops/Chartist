from typing import Any
from datetime import datetime
from django.test import TestCase
from scraper.mapper import parliamentary_item_from_dto
from scraper.dto import AgendapuntZaakBesluitVolgordeDTO
from scraper.tests.fixtures.utils_fixtures import BESLUIT_API_RESPONSE


class TestParliamentaryItemFromDto(TestCase):
    def test_parliamentary_item_from_dto_year_from_item_(self) -> None:
        # Make sure the year is correctly extracted from the item and
        # not its linked zaak.
        data: dict[str, Any] = BESLUIT_API_RESPONSE[1]
        azb_dto: AgendapuntZaakBesluitVolgordeDTO = (
            AgendapuntZaakBesluitVolgordeDTO.from_api(data)
        )
        result = parliamentary_item_from_dto(azb_dto)
        fetched_date = result.get("date")
        assert isinstance(fetched_date, datetime)
        self.assertEqual(
            "2025-12-17T13:18:36.047000+01:00", fetched_date.isoformat()
        )
