from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
import xml.etree.ElementTree as ET
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
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
MOTION_XML_URL: str = "https://zoek.officielebekendmakingen.nl/{}.xml"

# (connect, read) timeouts in seconds. Motion XML documents occasionally stall
# server-side; a short read timeout plus a retry recovers faster than waiting.
API_TIMEOUT: tuple[int, int] = (10, 60)
MOTION_XML_TIMEOUT: tuple[int, int] = (5, 15)

# Number of motion texts downloaded in parallel. Kept low to stay polite
# towards officielebekendmakingen.nl.
MAX_TEXT_WORKERS: int = 4

MOTION_START_MARKER: str = "gehoord de beraadslaging"
# Used when a motion omits 'gehoord de beraadslaging'. Compared to the whole
# line, so content lines that merely start with 'De Kamer' do not match.
MOTION_ALT_START_MARKER: str = "de kamer"
# Matched anywhere in the line; some motions drop the leading 'en'.
MOTION_END_MARKER: str = "gaat over tot de orde van de dag"
MOTION_FALLBACK_PREFIXES: tuple[str, ...] = (
    "constaterende",
    "overwegende",
    "verzoekt",
    "spreekt uit",
)

# Called as progress(stage, done, total).
ProgressCallback = Callable[[str, int, int], None]


def build_session() -> requests.Session:
    """
    Create a requests Session with connection pooling and automatic retries.

    Retries connection errors, read timeouts and 429/5xx responses with
    exponential backoff, honouring Retry-After headers.

    Returns:
        requests.Session: The configured session.
    """
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=MAX_TEXT_WORKERS)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def extract_motion_bullet_points(
    xml_content: bytes, document_id: str | None = None
) -> list[str]:
    """Extract the content lines from motion XML.

    Accepts raw bytes so that ElementTree can read the encoding declaration
    and handle the UTF-8 BOM correctly.

    Motions follow a fixed formula: 'De Kamer, gehoord de beraadslaging,'
    followed by the considerations and operative part, closed by 'en gaat
    over tot de orde van de dag.' and the signatories. All lines between
    those two markers are returned, regardless of their wording. When
    'gehoord de beraadslaging' is missing, 'De Kamer,' is used as the start.

    If either marker is missing, falls back to keeping only lines starting
    with constaterende, overwegende, verzoekt or spreekt uit.

    Trailing commas are stripped from each line.

    Args:
        xml_content (bytes): Raw XML bytes of the motion document.
        document_id (str | None): Optional identifier, used for logging.

    Returns:
        list[str]: Extracted lines.
    """
    root = ET.fromstring(xml_content)
    lines = [
        text
        for elem in root.iter("al")
        if (text := "".join(elem.itertext()).strip().rstrip(","))
    ]
    lowered = [line.lower() for line in lines]

    start = next(
        (i for i, s in enumerate(lowered) if s.startswith(MOTION_START_MARKER)),
        None,
    )
    if start is None:
        start = next(
            (i for i, s in enumerate(lowered) if s == MOTION_ALT_START_MARKER),
            None,
        )
    end = next(
        (
            i
            for i, s in enumerate(lowered)
            if MOTION_END_MARKER in s and start is not None and i > start
        ),
        None,
    )
    if start is not None and end is not None:
        return lines[start + 1 : end]

    if lines:
        logger.info(
            f"Motion markers not found in {document_id}, using prefix fallback",
            extra={"document_id": document_id},
        )
    return [
        line
        for line, low in zip(lines, lowered)
        if low.startswith(MOTION_FALLBACK_PREFIXES)
    ]


@dataclass
class VoteImportResult:
    """
    Summary of a vote import run.

    Attributes:
        motions (int): Number of motions with a decision that were processed.
        created (int): Number of newly created parliamentary items.
        texts_fetched (int): Number of motion texts downloaded and stored.
        texts_failed (int): Number of motion texts that could not be fetched.
    """

    motions: int = 0
    created: int = 0
    texts_fetched: int = 0
    texts_failed: int = 0


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

    def __init__(self, progress: ProgressCallback | None = None) -> None:
        """
        Initialize the ParliamentApi client.

        Args:
            progress (ProgressCallback | None): Optional callback invoked as
                progress(stage, done, total) while importing.
        """
        self.api_url: str = API_URL
        self.session: requests.Session = build_session()
        self.progress: ProgressCallback | None = progress

    def _report(self, stage: str, done: int, total: int) -> None:
        if self.progress:
            self.progress(stage, done, total)

    def fetch(
        self,
        object_name: str,
        filters: list[str] | None = None,
        expand: list[str] | None = None,
        order_by: str | None = None,
        top: int | None = None,
        stage: str | None = None,
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
            stage (str | None): Optional progress stage name. When given,
                progress is reported per page.

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
            "$count": "true" if stage else None,
        }
        params = {k: v for k, v in params.items() if v is not None}

        # Iterate over pages
        items: list[dict[str, Any]] = []
        while True:
            r = self.session.get(url, params=params, timeout=API_TIMEOUT)
            r.raise_for_status()
            payload = r.json()
            items.extend(payload.get("value", []))
            if stage:
                total = payload.get("@odata.count", len(items))
                self._report(stage, len(items), max(total, len(items)))

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

    def import_votes(self, refetch_texts: bool = False) -> VoteImportResult:
        """
        Fetch parliamentary motions and associated votes from the API.

        Retrieves Zaak records of type Motie with their nested Besluit and
        Stemming data, links votes to parties, and updates or creates
        corresponding `ParliamentaryItem` and `PartyVote` model instances.

        Afterwards, downloads the motion text for new items and items
        without text (or all items when `refetch_texts` is set), using a
        small thread pool. Failed downloads are logged and skipped. Nothing
        is stored about the failure: the item simply keeps no text, so the
        next run selects it again.

        Each item is saved in its own atomic transaction.
        Skips votes for unknown parties.

        Parties that did not vote (and are not included in the data, even as
        abstains) are marked as abstaining.

        Args:
            refetch_texts (bool): Re-download the text of every motion, also
                those that already have text.

        Returns:
            VoteImportResult: Counts of processed items and fetched texts.
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
            stage="Fetching motions",
        )
        party_lookup = {p.api_id: p for p in Party.objects.all()}
        result = VoteImportResult()

        to_process = [data for data in vote_data if data.get("Besluit")]
        text_todo: list[tuple[ParliamentaryItem, str]] = []
        for i, data in enumerate(to_process, start=1):
            self._report("Saving votes", i, len(to_process))
            try:
                dto: ZaakBesluitDTO = ZaakBesluitDTO.from_api(data)
            except ValueError as e:
                logger.warning(
                    f"Skipping invalid Zaak record {data.get('Id')}: {e}",
                    extra={"zaak_id": data.get("Id"), "error": str(e)},
                )
                continue

            result.motions += 1
            with transaction.atomic():
                (
                    parliamentary_item,
                    created,
                ) = ParliamentaryItem.objects.update_or_create(
                    api_id=dto.Id,
                    defaults=parliamentary_item_from_dto(dto),
                )
                if created:
                    result.created += 1
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

            if (
                refetch_texts or created or not parliamentary_item.text
            ) and dto.Document:
                externe_id = (
                    dto.Document[0]
                    .get("HuidigeDocumentVersie", {})
                    .get("ExterneIdentifier")
                )
                if externe_id:
                    text_todo.append((parliamentary_item, externe_id))

        self._import_texts(text_todo, result)
        return result

    def _fetch_motion_text(self, externe_id: str) -> list[str]:
        """
        Download a motion document and extract its content lines.

        Args:
            externe_id (str): The document identifier, e.g. 'kst-36848-53'.

        Returns:
            list[str]: The extracted lines.

        Raises:
            requests.exceptions.RequestException: If the download fails.
            xml.etree.ElementTree.ParseError: If the document is not valid XML.
        """
        response = self.session.get(
            MOTION_XML_URL.format(externe_id), timeout=MOTION_XML_TIMEOUT
        )
        response.raise_for_status()
        return extract_motion_bullet_points(
            response.content, document_id=externe_id
        )

    def _import_texts(
        self,
        text_todo: list[tuple[ParliamentaryItem, str]],
        result: VoteImportResult,
    ) -> None:
        """
        Download motion texts in parallel and store them.

        Downloads run in a thread pool; database writes happen on the calling
        thread. Failures are logged and counted, not raised.

        Args:
            text_todo (list[tuple[ParliamentaryItem, str]]): Items paired with
                their document identifier.
            result (VoteImportResult): Result object to update with counts.
        """
        with ThreadPoolExecutor(max_workers=MAX_TEXT_WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_motion_text, externe_id): (
                    item,
                    externe_id,
                )
                for item, externe_id in text_todo
            }
            for i, future in enumerate(as_completed(futures), start=1):
                item, externe_id = futures[future]
                try:
                    item.text = future.result()
                except (
                    requests.exceptions.RequestException,
                    ET.ParseError,
                ) as e:
                    result.texts_failed += 1
                    logger.warning(
                        f"Failed to fetch motion text {externe_id}: {e}",
                        extra={"document_id": externe_id, "error": str(e)},
                    )
                else:
                    item.save(update_fields=["text"])
                    result.texts_fetched += 1
                self._report("Fetching motion texts", i, len(text_todo))
