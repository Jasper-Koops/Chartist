from typing import Any
import requests
from scraper.models import Party, PartyVote, ParliamentaryItem, VoteType
from scraper.dto import (
    FractieDTO,
    AgendapuntZaakBesluitVolgordeDTO,
    StemmingDTO,
)
from scraper.mapper import (
    party_from_dto,
    parliamentary_item_from_dto,
    party_vote_from_dto,
)
from django.db import transaction


API_URL: str = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"


class ParliamentApi:
    """
    API client for the Dutch Parliament OData API.

    Methods:
        - fetch: Generic method to fetch data from a specified object with
            optional filters, expansions, ordering, and top limit.
        - import_parties: Imports party data from the API into the local
            database.
        - import_votes: Fetches and processes 'Besluit' data, linking it to
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
                "Fractie", "Besluit").
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
            r = requests.get(url, params=params)
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
                fractie_dto: FractieDTO = FractieDTO.from_api(data)

                try:
                    Party.objects.update_or_create(
                        api_id=fractie_dto.Id,
                        defaults=party_from_dto(fractie_dto),
                    )
                except Exception:
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
        Fetch parliamentary decisions and associated votes from the API.

        Retrieves data about decisions and their related votes, links them to parties,
        and updates or creates corresponding `ParliamentaryItem` and `PartyVote` model
        instances in the database.

        Ensures database integrity by using an atomic transaction.
        Skips votes for unknown parties.

        Parties that did not vote (and are not included in the data, even as
        abstains) are marked as abstaining.
        """
        filters: list[str] = [
            "GewijzigdOp gt 2025-11-01T00:00:00+01:00",
            "StemmingsSoort ne null",
        ]
        order_by: str = ""
        expand: list[str] = [
            "Zaak($filter=Soort eq 'Motie')",
            "Stemming($filter=Vergissing eq false;$select=Soort,Fractie_Id)",
        ]
        vote_data = self.fetch(
            object_name="Besluit",
            filters=filters,
            order_by=order_by,
            expand=expand,
        )
        party_lookup = {p.api_id: p for p in Party.objects.all()}

        with transaction.atomic():
            for data in vote_data:
                # Skip if no Zaak linked
                if not data.get("Zaak"):
                    continue
                azb_dto: AgendapuntZaakBesluitVolgordeDTO = (
                    AgendapuntZaakBesluitVolgordeDTO.from_api(data)
                )
                parliamentary_item: ParliamentaryItem = (
                    ParliamentaryItem.objects.update_or_create(
                        api_id=azb_dto.Zaak[0].Id,
                        defaults=parliamentary_item_from_dto(azb_dto),
                    )[0]
                )

                # Not all parties participated in each vote. Those parties
                # are not always marked as 'abstain', so we need to track which
                # parties have voted and do this ourselves.
                seen_party_ids: set[str] = set()
                stemming_dto: StemmingDTO
                for stemming_dto in azb_dto.Stemming:

                    party = party_lookup.get(stemming_dto.Fractie_Id)
                    if party is None:
                        print(
                            "Skipping unknown party with id:",
                            stemming_dto.Fractie_Id,
                        )
                        continue
                    seen_party_ids.add(stemming_dto.Fractie_Id)

                    PartyVote.objects.update_or_create(
                        party=party_lookup[stemming_dto.Fractie_Id],
                        parliamentary_item=parliamentary_item,
                        defaults=party_vote_from_dto(stemming_dto),
                    )

                # Parse abstains for parties that did not vote and mark them
                # as abstain.
                for party_id, party in party_lookup.items():
                    if party_id in seen_party_ids:
                        continue

                    PartyVote.objects.create(
                        party=party,
                        parliamentary_item=parliamentary_item,
                        vote=VoteType.ABSTAIN,
                    )
