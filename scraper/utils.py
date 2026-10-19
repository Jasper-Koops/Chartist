from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, cast
import xml.etree.ElementTree as ET
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from scraper.models import (
    ImportRun,
    ImportRunStatus,
    Party,
    PartyAlias,
    PartySuccession,
    PartyVote,
    ParliamentaryItem,
    ParliamentaryItemStatusTypes,
    VoteType,
)
from scraper.dto import (
    FractieDTO,
    ZaakBesluitDTO,
    StemmingDTO,
)
from scraper.mapper import (
    document_id_from_dto,
    party_from_dto,
    parliamentary_item_from_dto,
)
from scraper.text import extract_motion_text
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


API_URL: str = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/"
MOTION_XML_URL: str = "https://zoek.officielebekendmakingen.nl/{}.xml"

# Start of the analysed period: installation of the current parliament.
PERIOD_START: str = "2025-11-12T00:00:00+01:00"

# A successor must start within this many days of its predecessor ending,
# and share at least this share of members in both directions. Strict on
# purpose: only a continuation under a new identity (e.g. GroenLinks-PvdA
# -> PRO) qualifies, not a split or a merger.
SUCCESSION_MAX_GAP_DAYS: int = 7
SUCCESSION_MIN_MEMBER_OVERLAP: float = 0.9

# (connect, read) timeouts in seconds. Motion XML documents occasionally stall
# server-side; a short read timeout plus a retry recovers faster than waiting.
API_TIMEOUT: tuple[int, int] = (10, 60)
MOTION_XML_TIMEOUT: tuple[int, int] = (5, 15)

# Number of motion texts downloaded in parallel. Kept low to stay polite
# towards officielebekendmakingen.nl.
MAX_TEXT_WORKERS: int = 4

# Called as progress(stage, done, total).
ProgressCallback = Callable[[str, int, int], None]


def build_session() -> requests.Session:
    """
    Create a requests Session with connection pooling and automatic retries.

    Retries GET requests up to 3 times on connection errors, read timeouts
    and 429, 500, 502, 503 and 504 responses, with exponential backoff,
    honouring Retry-After headers.

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


def aggregate_party_votes(stemmingen: list[StemmingDTO]) -> dict[str, VoteType]:
    """
    Reduce vote records to a single vote per party.

    A vote by show of hands ('Met handopsteken') has one record per party. A
    roll-call vote ('Hoofdelijk') has one record per member, so a party can
    have many records, including members who did not take part.

    The party vote is the majority of FOR and AGAINST votes among its members;
    members who did not take part are ignored. If no member took part, or the
    party is split evenly, the party vote is ABSTAIN.

    Args:
        stemmingen (list[StemmingDTO]): The vote records of a decision.

    Returns:
        dict[str, VoteType]: The vote per party, keyed by Fractie_Id.
    """
    counts: defaultdict[str, Counter[VoteType]] = defaultdict(Counter)
    for stemming in stemmingen:
        counts[stemming.Fractie_Id][VoteType(stemming.Soort)] += 1

    votes: dict[str, VoteType] = {}
    for fractie_id, count in counts.items():
        if count[VoteType.FOR] > count[VoteType.AGAINST]:
            votes[fractie_id] = VoteType.FOR
        elif count[VoteType.AGAINST] > count[VoteType.FOR]:
            votes[fractie_id] = VoteType.AGAINST
        else:
            votes[fractie_id] = VoteType.ABSTAIN
    return votes


@dataclass
class VoteImportResult:
    """
    Summary of a vote import run.

    Attributes:
        motions (int): Number of motions with a decision that were processed.
        created (int): Number of newly created parliamentary items.
        votes_created (int): Number of party votes added.
        votes_updated (int): Number of party votes that changed.
        votes_deleted (int): Number of party votes removed.
        stale (int): Number of stored items that no longer have a vote in the
            API; their votes were removed and their status reset to pending.
        texts_fetched (int): Number of motion texts downloaded and stored.
        texts_failed (int): Number of motion texts that could not be
            downloaded or parsed.
    """

    motions: int = 0
    created: int = 0
    votes_created: int = 0
    votes_updated: int = 0
    votes_deleted: int = 0
    stale: int = 0
    texts_fetched: int = 0
    texts_failed: int = 0

    @property
    def has_vote_changes(self) -> bool:
        """Whether this run changed any votes, i.e. the analysis input."""
        return bool(
            self.votes_created
            or self.votes_updated
            or self.votes_deleted
            or self.stale
        )


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
                `$count=true` is requested and progress is reported per page.

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
        Import parties from the API into the local database.

        Imports every party that was active at some point since PERIOD_START,
        so the votes of parties that ended during the period (e.g. a party
        continued under a new name) can still be linked.

        Fetches party data from the API, converts it into DTOs, and updates or
        creates corresponding `Party` model instances in the database.

        A party registered again under a new API id keeps its local record
        (see `_adopt_reregistration`).

        A record that fails is logged and skipped; the others are still
        saved (`update_or_create` uses its own savepoint).
        """
        filters: list[str] = [
            "Verwijderd eq false",
            f"(DatumInactief eq null or DatumInactief ge {PERIOD_START})",
        ]
        party_data: list[dict[str, str | int | None | bool]] = self.fetch(
            object_name="Fractie", filters=filters, order_by=None
        )
        active_ids = {str(data.get("Id")) for data in party_data}
        with transaction.atomic():
            for data in party_data:
                try:
                    fractie_dto: FractieDTO = FractieDTO.from_api(data)
                    self._adopt_reregistration(fractie_dto, active_ids)
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

    def _adopt_reregistration(
        self, fractie_dto: FractieDTO, active_ids: set[str]
    ) -> None:
        """
        Link a party registered again under a new API id to its local record.

        When no local party has the new id, but one has the same abbreviation
        and an id that is no longer active, it is the same party: the local
        record takes the new id and keeps the old one as an alias, because
        the API may still record votes under it (as for 50PLUS).

        Args:
            fractie_dto (FractieDTO): The party as returned by the API.
            active_ids (set[str]): Ids of all parties active in the period.
        """
        if Party.objects.filter(api_id=fractie_dto.Id).exists():
            return
        existing = (
            Party.objects.filter(abbreviation=fractie_dto.Afkorting)
            .exclude(api_id__in=active_ids)
            .first()
        )
        if existing is None:
            return
        PartyAlias.objects.get_or_create(
            api_id=existing.api_id, defaults={"party": existing}
        )
        logger.info(
            f"Party {existing.abbreviation} registered again: id "
            f"{existing.api_id} -> {fractie_dto.Id}, old id kept as alias",
            extra={"old_id": existing.api_id, "new_id": fractie_dto.Id},
        )
        existing.api_id = fractie_dto.Id
        existing.save(update_fields=["api_id"])

    def _resolve_unknown_parties(
        self, fractie_ids: set[str], party_lookup: dict[str, Party]
    ) -> None:
        """
        Find aliases for party ids that votes reference but no party has.

        An unknown id whose API record is inactive and has the abbreviation
        of a known party is an older id of that party: it is stored as an
        alias and added to `party_lookup`. Other ids stay unknown.

        Args:
            fractie_ids (set[str]): Unknown party ids referenced by votes.
            party_lookup (dict[str, Party]): Party per API id; updated.
        """
        by_abbreviation = {
            party.abbreviation: party for party in set(party_lookup.values())
        }
        for fractie_id in sorted(fractie_ids):
            records = self.fetch(
                object_name="Fractie", filters=[f"Id eq {fractie_id}"]
            )
            if not records:
                continue
            record = records[0]
            party = by_abbreviation.get(str(record.get("Afkorting")))
            if party is None or not record.get("DatumInactief"):
                continue
            PartyAlias.objects.get_or_create(
                api_id=fractie_id, defaults={"party": party}
            )
            party_lookup[fractie_id] = party
            logger.info(
                f"Votes reference an older id {fractie_id} of "
                f"{party.abbreviation}; stored as alias",
                extra={"alias": fractie_id, "party": party.api_id},
            )

    def _members(self, fractie_id: str, on: date) -> set[str]:
        """
        Get the members (Persoon ids) of a party on a given date.

        Args:
            fractie_id (str): The party's API id.
            on (date): The date to get the members for.

        Returns:
            set[str]: The Persoon ids of the members on that date.
        """
        # Expanded rows contain nested lists, unlike fetch's flat row type.
        seats = cast(
            list[dict[str, Any]],
            self.fetch(
                object_name="FractieZetel",
                filters=["Verwijderd eq false", f"Fractie_Id eq {fractie_id}"],
                expand=[
                    "FractieZetelPersoon($filter=Verwijderd eq false;"
                    "$select=Persoon_Id,Van,TotEnMet)"
                ],
            ),
        )
        day = on.isoformat()
        members: set[str] = set()
        for seat in seats:
            for member in seat.get("FractieZetelPersoon") or []:
                start = str(member["Van"])[:10]
                end = member["TotEnMet"]
                if start <= day and (end is None or str(end)[:10] >= day):
                    members.add(str(member["Persoon_Id"]))
        return members

    def import_successions(self) -> int:
        """
        Detect parties that continue another party under a new identity.

        A party B succeeds a party A when A ended at most
        SUCCESSION_MAX_GAP_DAYS from B's start, and at least
        SUCCESSION_MIN_MEMBER_OVERLAP of A's last members are B's first
        members and vice versa. A split (the original party continues) or a
        merger (members come from several parties) does not qualify.

        Only parties that exist locally are considered. Detected successions
        are created or updated, never deleted, so corrections made in the
        admin are kept unless the data contradicts them.

        Returns:
            int: The number of successions detected.
        """
        fracties = self.fetch(
            object_name="Fractie",
            filters=[
                "Verwijderd eq false",
                f"(DatumActief ge {PERIOD_START} "
                f"or DatumInactief ge {PERIOD_START})",
            ],
        )
        parties = {p.api_id: p for p in Party.objects.all()}

        def day(value: Any) -> date:
            return datetime.fromisoformat(str(value)).date()

        ended = [
            f for f in fracties if f.get("DatumInactief") and f["Id"] in parties
        ]
        started = [
            f
            for f in fracties
            if f.get("DatumActief")
            and day(f["DatumActief"]) >= day(PERIOD_START)
            and f["Id"] in parties
        ]

        detected = 0
        for old in ended:
            end = day(old["DatumInactief"])
            for new in started:
                start = day(new["DatumActief"])
                if new["Id"] == old["Id"] or (
                    abs((start - end).days) > SUCCESSION_MAX_GAP_DAYS
                ):
                    continue
                before = self._members(str(old["Id"]), end - timedelta(days=1))
                after = self._members(str(new["Id"]), start + timedelta(days=1))
                if not before or not after:
                    continue
                shared = len(before & after)
                overlap = min(shared / len(before), shared / len(after))
                if overlap < SUCCESSION_MIN_MEMBER_OVERLAP:
                    continue
                PartySuccession.objects.update_or_create(
                    predecessor=parties[str(old["Id"])],
                    defaults={
                        "successor": parties[str(new["Id"])],
                        "date": start,
                        "member_overlap": overlap,
                    },
                )
                detected += 1
                logger.info(
                    f"Detected succession {old['Afkorting']} -> "
                    f"{new['Afkorting']} ({overlap:.0%} shared members)",
                    extra={"predecessor": old["Id"], "successor": new["Id"]},
                )
        return detected

    def import_votes(self, refetch_texts: bool = False) -> VoteImportResult:
        """
        Fetch parliamentary motions and associated votes from the API.

        Retrieves Zaak records of type Motie with their nested Besluit and
        Stemming data, and updates or creates the corresponding
        `ParliamentaryItem` instances.

        The votes of every motion are synced with the API on every run: all
        stored votes are loaded in one query, compared with the downloaded
        votes, and only the differences are written. Stored items that are no
        longer returned with a vote (e.g. a vote that was annulled and the
        motion postponed) lose their votes and are reset to pending. Items
        whose API record fails validation are left untouched.

        Afterwards, downloads the motion text for new items and items
        without text (or all items when `refetch_texts` is set), using a
        small thread pool. Failed downloads are logged and skipped; the item
        keeps its current text, so an item without text is selected again on
        the next run.

        Items are saved one by one; vote changes are written together at the
        end in one atomic transaction; texts are saved afterwards. An
        interrupted run is repaired by the next one.
        Skips votes for unknown parties.

        Each party gets one vote; for roll-call votes this is the majority of
        its members (see `aggregate_party_votes`). Votes a party later marked
        as a mistake ('Vergissing') are included: the cast vote stands.
        Votes recorded as 'Niet deelgenomen' are stored as abstentions.
        Parties missing from the vote data get no `PartyVote`.

        Args:
            refetch_texts (bool): Re-download the text of every motion that
                has a document, also those that already have text.

        Returns:
            VoteImportResult: Counts of processed items, vote changes and
                fetched texts.
        """
        filters: list[str] = [
            "Verwijderd eq false",
            "Soort eq 'Motie'",
            f"GestartOp gt {PERIOD_START}",
        ]
        expand: list[str] = [
            "Besluit($filter=Verwijderd eq false and StemmingsSoort ne null;"
            "$expand=Stemming($filter=Verwijderd eq false;$select=Soort,Fractie_Id),"
            "Agendapunt($select=Id;$expand=Activiteit($select=Datum));"
            "$select=Id,Agendapunt_Id,BesluitSoort,GewijzigdOp)",
            "Document($expand=HuidigeDocumentVersie($select=ExterneIdentifier);$select=Id)",
        ]
        vote_data = self.fetch(
            object_name="Zaak",
            filters=filters,
            expand=expand,
            stage="Fetching motions",
        )
        # Party per API id, including older ids stored as aliases.
        party_lookup: dict[str, Party] = {
            p.api_id: p for p in Party.objects.all()
        }
        party_lookup.update(
            {
                alias.api_id: alias.party
                for alias in PartyAlias.objects.select_related("party")
            }
        )
        # Expanded rows contain nested lists, unlike fetch's flat row type.
        referenced = {
            str(stemming.get("Fractie_Id"))
            for zaak in cast(list[dict[str, Any]], vote_data)
            for besluit in zaak.get("Besluit") or []
            for stemming in besluit.get("Stemming") or []
        }
        self._resolve_unknown_parties(
            referenced - set(party_lookup), party_lookup
        )
        result = VoteImportResult()

        stored_votes: defaultdict[int, dict[int, PartyVote]] = defaultdict(dict)
        for party_vote in PartyVote.objects.only(
            "id", "party_id", "parliamentary_item_id", "vote"
        ):
            stored_votes[party_vote.parliamentary_item_id][
                party_vote.party_id
            ] = party_vote
        votes_to_create: list[PartyVote] = []
        votes_to_update: list[PartyVote] = []
        vote_ids_to_delete: list[int] = []
        unknown_parties: Counter[str] = Counter()
        # Api ids of items that are present in the download, with or without
        # a valid vote; everything else stored is stale.
        seen_api_ids: set[str] = set()

        to_process = [data for data in vote_data if data.get("Besluit")]
        text_todo: list[tuple[ParliamentaryItem, str]] = []
        for i, data in enumerate(to_process, start=1):
            self._report("Syncing votes", i, len(to_process))
            try:
                dto: ZaakBesluitDTO = ZaakBesluitDTO.from_api(data)
            except ValueError as e:
                seen_api_ids.add(str(data.get("Id")))
                logger.warning(
                    f"Skipping invalid Zaak record {data.get('Id')}: {e}",
                    extra={"zaak_id": data.get("Id"), "error": str(e)},
                )
                continue

            seen_api_ids.add(dto.Id)
            result.motions += 1
            (
                parliamentary_item,
                created,
            ) = ParliamentaryItem.objects.update_or_create(
                api_id=dto.Id,
                defaults=parliamentary_item_from_dto(dto),
            )
            if created:
                result.created += 1

            # Count votes under an alias as the party's own, before taking
            # the majority, so one party never gets two votes on an item.
            stemmingen = [
                (
                    StemmingDTO(
                        Soort=stemming.Soort,
                        Fractie_Id=party_lookup[stemming.Fractie_Id].api_id,
                    )
                    if stemming.Fractie_Id in party_lookup
                    else stemming
                )
                for stemming in dto.Besluit[0].Stemming
            ]
            desired: dict[int, VoteType] = {}
            for fractie_id, vote in aggregate_party_votes(stemmingen).items():
                party = party_lookup.get(fractie_id)
                if party is None:
                    unknown_parties[fractie_id] += 1
                    continue
                desired[party.id] = vote

            current = stored_votes.get(parliamentary_item.id, {})
            for party_id, vote in desired.items():
                stored = current.get(party_id)
                if stored is None:
                    votes_to_create.append(
                        PartyVote(
                            party_id=party_id,
                            parliamentary_item=parliamentary_item,
                            vote=vote,
                        )
                    )
                elif stored.vote != vote:
                    stored.vote = vote
                    votes_to_update.append(stored)
            vote_ids_to_delete.extend(
                stored.id
                for party_id, stored in current.items()
                if party_id not in desired
            )

            if refetch_texts or created or not parliamentary_item.text:
                externe_id = document_id_from_dto(dto)
                if externe_id:
                    text_todo.append((parliamentary_item, externe_id))

        for fractie_id, count in unknown_parties.items():
            logger.info(
                f"Skipped {count} votes of unknown party {fractie_id}",
                extra={"party_id": fractie_id, "count": count},
            )

        # Guard against wiping every vote if the API returned nothing.
        stale_items = (
            ParliamentaryItem.objects.exclude(api_id__in=seen_api_ids)
            if seen_api_ids
            else ParliamentaryItem.objects.none()
        )
        with transaction.atomic():
            PartyVote.objects.bulk_create(votes_to_create)
            PartyVote.objects.bulk_update(votes_to_update, ["vote"])
            PartyVote.objects.filter(id__in=vote_ids_to_delete).delete()
            stale_votes = PartyVote.objects.filter(
                parliamentary_item__in=stale_items
            )
            stale_ids = list(
                stale_votes.values_list(
                    "parliamentary_item_id", flat=True
                ).distinct()
            )
            result.votes_deleted += stale_votes.delete()[0]
            result.stale = ParliamentaryItem.objects.filter(
                id__in=stale_ids
            ).update(status=ParliamentaryItemStatusTypes.PENDING)

        result.votes_created += len(votes_to_create)
        result.votes_updated += len(votes_to_update)
        result.votes_deleted += len(vote_ids_to_delete)

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
        return extract_motion_text(response.content, document_id=externe_id)

    def _import_texts(
        self,
        text_todo: list[tuple[ParliamentaryItem, str]],
        result: VoteImportResult,
    ) -> None:
        """
        Download motion texts in parallel and store them.

        Downloads run in a thread pool; database writes happen on the calling
        thread. Network and XML parse errors are logged and counted, not
        raised; other exceptions propagate.

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


def run_import(
    api: ParliamentApi,
    refetch_texts: bool = False,
    announce: Callable[[str], None] | None = None,
) -> VoteImportResult:
    """
    Run a full sync with the Parliament API and record it as an ImportRun.

    Imports parties, detects successions and imports votes. The run is
    stored as running, then marked succeeded with the import's counts, or
    failed with the error (which is re-raised).

    Args:
        api (ParliamentApi): The client to import with.
        refetch_texts (bool): Passed on to `ParliamentApi.import_votes`.
        announce (Callable[[str], None] | None): Optional callback for stage
            messages, e.g. to print them.

    Returns:
        VoteImportResult: The counts of the vote import.
    """
    run = ImportRun.objects.create()

    def say(message: str) -> None:
        if announce:
            announce(message)

    try:
        say("Importing party data")
        api.import_parties()
        api.import_successions()
        say("Importing vote data")
        result = api.import_votes(refetch_texts=refetch_texts)
    except Exception as e:
        run.status = ImportRunStatus.FAILED
        run.error = f"{type(e).__name__}: {e}"
        run.finished_at = timezone.now()
        run.save()
        raise

    run.status = ImportRunStatus.SUCCEEDED
    run.finished_at = timezone.now()
    for field, value in asdict(result).items():
        setattr(run, field, value)
    run.save()
    return result
