from typing import Any
import xml.etree.ElementTree as ET
import requests
from scraper.models import Party, PartyVote, ParliamentaryItem
from scraper.dto import (
    FractieDTO,
    ZaakBesluitDTO,
    StemmingDTO,
)
from scraper.mapper import (
    party_from_dto,
    parliamentary_item_from_dto,
    party_vote_from_dto,
)
from django.db import transaction
import logging


logger = logging.getLogger(__name__)


API_URL: str = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"


def extract_motion_bullet_points(xml_content: bytes) -> list[str]:
    """Extract key bullet points from motion XML.

    Accepts raw bytes so that ElementTree can read the encoding declaration
    and handle the UTF-8 BOM correctly.

    Filters on lines starting with constaterende, overwegende, verzoekt,
    or spreekt uit. Strips trailing commas. Excludes boilerplate lines such
    as 'De Kamer,', 'gehoord de beraadslaging,', author names, and
    'en gaat over tot de orde van de dag.' by prefix matching.

    Args:
        xml_content (bytes): Raw XML bytes of the motion document.

    Returns:
        list[str]: Extracted bullet point strings.
    """
    prefixes = ["constaterende", "overwegende", "verzoekt", "spreekt uit"]
    root = ET.fromstring(xml_content)
    bullets = []
    for elem in root.iter("al"):
        text = "".join(elem.itertext()).strip().rstrip(",")
        if text and any(text.lower().startswith(p) for p in prefixes):
            bullets.append(text)
    return bullets


class ParliamentApi:
    """
    API client for the Dutch Parliament OData API.

    Methods:
        - fetch: Generic method to fetch data from a specified object with
            optional filters, expansions, ordering, and top limit.
        - import_parties: Imports party data from the API into the local
            database.
        - import_votes: Fetches and processes 'Zaak' data, linking it to
            parliamentary items and party votes.
    """

    def __init__(self) -> None:
        """
        Initialize the ParliamentApi client with the base API URL.
        """
        self.api_url: str = API_URL

    def fetch(
        self,
        object_name: str,
        filters: list[str] | None = None,
        expand: list[str] | None = None,
        order_by: str | None = None,
        top: int | None = None,
    ) -> list[dict[str, str | int | None | bool]]:
        """
        Fetch data from the Dutch Parliament OData API.

        Args:
            object_name (str): The name of the object to fetch (e.g.,
                "Fractie", "Zaak").
            filters (list[str] | None): Optional list of OData filter strings.
            expand (list[str] | None): Optional list of related entities to
                expand.
            order_by (str | None): Optional field to order the results by.
            top (int | None): Optional limit on the number of results to fetch.

        Returns:
            list[dict[str, str | int | None | bool]]: A list of dictionaries
            representing the fetched data.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """

        # Get base url
        url = f"{self.api_url}{object_name}"

        # Include url parameters
        params = {
            "$format": "application/json",
            "$filter": " and ".join(filters) if filters else None,
            "$expand": ",".join(expand) if expand else None,
            "$orderby": order_by if order_by else None,
            "$top": str(top) if top else None,
        }
        params = {k: v for k, v in params.items() if v is not None}

        # Iterate over pages
        items: list[dict[str, Any]] = []
        while True:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            payload = r.json()
            items.extend(payload.get("value", []))

            next_page = payload.get("@odata.nextLink")
            if not next_page:
                break

            url, params = next_page, {}

        return items

    def import_parties(self) -> None:
        """
        Import active parties from the API into the local database.

        Fetches party data from the API, converts it into DTOs, and updates or
        creates corresponding `Party` model instances in the database.

        Ensures database integrity by using an atomic transaction.
        """
        filters: list[str] = ["Verwijderd eq false", "DatumInactief eq null"]
        party_data: list[dict[str, str | int | None | bool]] = self.fetch(
            object_name="Fractie", filters=filters, order_by=None
        )
        with transaction.atomic():
            for data in party_data:
                try:
                    fractie_dto: FractieDTO = FractieDTO.from_api(data)
                    Party.objects.update_or_create(
                        api_id=fractie_dto.Id,
                        defaults=party_from_dto(fractie_dto),
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to import party data for {data.get('NaamNL')} with id {data.get('Id')}: {e}",
                        extra={
                            "party_id": data.get("Id"),
                            "party_name": data.get("NaamNL"),
                            "error": str(e),
                        },
                    )
                    continue

        # FIXME - remove when bug fixed
        try:
            vijftigplus = Party.objects.get(abbreviation="50PLUS")
            vijftigplus.api_id = "a34bf6c8-834e-4dba-b4d2-f2f1b3957bd2"
            vijftigplus.save()
        except Party.DoesNotExist:
            pass

    def import_votes(self) -> None:
        """
        Fetch parliamentary motions and associated votes from the API.

        Retrieves Zaak records of type Motie with their nested Besluit and
        Stemming data, links votes to parties, and updates or creates
        corresponding `ParliamentaryItem` and `PartyVote` model instances.

        For newly created items, fetches the motion text via DocumentVersie
        and logs the extracted bullet points at DEBUG level.

        Ensures database integrity by using an atomic transaction.
        Skips votes for unknown parties.

        Parties that did not vote (and are not included in the data, even as
        abstains) are marked as abstaining.
        """
        filters: list[str] = [
            "Verwijderd eq false",
            "Soort eq 'Motie'",
            "GestartOp gt 2025-11-12T00:00:00+01:00",
        ]
        expand: list[str] = [
            "Besluit($filter=Verwijderd eq false and StemmingsSoort ne null;"
            "$expand=Stemming($filter=Verwijderd eq false and Vergissing eq false;$select=Soort,Fractie_Id);"
            "$select=Id,Agendapunt_Id,BesluitSoort,GewijzigdOp)",
            "Document($expand=HuidigeDocumentVersie($select=ExterneIdentifier);$select=Id)",
        ]
        vote_data = self.fetch(
            object_name="Zaak",
            filters=filters,
            expand=expand,
        )
        party_lookup = {p.api_id: p for p in Party.objects.all()}

        for data in vote_data:
            if not data.get("Besluit"):
                continue
            try:
                dto: ZaakBesluitDTO = ZaakBesluitDTO.from_api(data)
            except ValueError as e:
                logger.warning(
                    f"Skipping invalid Zaak record {data.get('Id')}: {e}",
                    extra={"zaak_id": data.get("Id"), "error": str(e)},
                )
                continue

            with transaction.atomic():
                (
                    parliamentary_item,
                    created,
                ) = ParliamentaryItem.objects.update_or_create(
                    api_id=dto.Id,
                    defaults=parliamentary_item_from_dto(dto),
                )
                if created:
                    stemming_dto: StemmingDTO
                    for stemming_dto in dto.Besluit[0].Stemming:
                        party = party_lookup.get(stemming_dto.Fractie_Id)
                        if party is None:
                            logger.info(
                                f"Skipping unknown party with id {stemming_dto.Fractie_Id} during vote import",
                                extra={"party_id": stemming_dto.Fractie_Id},
                            )
                            continue

                        PartyVote.objects.update_or_create(
                            party=party_lookup[stemming_dto.Fractie_Id],
                            parliamentary_item=parliamentary_item,
                            defaults=party_vote_from_dto(stemming_dto),
                        )

            if (created or not parliamentary_item.text) and dto.Document:
                externe_id = (
                    dto.Document[0]
                    .get("HuidigeDocumentVersie", {})
                    .get("ExterneIdentifier")
                )
                if externe_id:
                    xml_resp = requests.get(
                        f"https://zoek.officielebekendmakingen.nl/{externe_id}.xml",
                        timeout=30,
                    )
                    if xml_resp.ok:
                        bullets = extract_motion_bullet_points(xml_resp.content)
                        parliamentary_item.text = bullets
                        parliamentary_item.save(update_fields=["text"])
