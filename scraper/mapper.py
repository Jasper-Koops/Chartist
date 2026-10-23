from datetime import date, datetime
from scraper.dto import (
    FractieDTO,
    ZaakBesluitDTO,
    StemmingDTO,
)


class ParliamentaryItemType:
    MOTION = "Motion"


def party_from_dto(fractie_dto: FractieDTO) -> dict[str, str]:
    return {
        "api_id": fractie_dto.Id,
        "name": fractie_dto.NaamNL,
        "abbreviation": fractie_dto.Afkorting,
    }


def parliamentary_item_from_dto(
    dto: ZaakBesluitDTO,
) -> dict[str, str | datetime | date | None]:
    return {
        "api_id": dto.Id,
        "title": dto.Onderwerp,
        "date": dto.Besluit[0].GewijzigdOp,
        "vote_date": dto.Besluit[0].VoteDate,
        "item_type": ParliamentaryItemType.MOTION,
        "status": dto.Besluit[0].BesluitSoort,
        "document_id": document_id_from_dto(dto),
    }


def document_id_from_dto(dto: ZaakBesluitDTO) -> str | None:
    """The motion document's identifier (e.g. 'kst-36848-53'), if known."""
    return document_source_from_dto(dto)["document_id"]


def document_source_from_dto(
    dto: ZaakBesluitDTO,
) -> dict[str, str | None]:
    """Version metadata used to detect changes to a motion's stored text."""
    if not dto.Document:
        return {"document_id": None, "version_id": None, "modified_at": None}
    version = dto.Document[0].get("HuidigeDocumentVersie") or {}
    externe_id = version.get("ExterneIdentifier")
    return {
        "document_id": str(externe_id) if externe_id else None,
        "version_id": str(version["Id"]) if version.get("Id") else None,
        "modified_at": (
            str(version["GewijzigdOp"]) if version.get("GewijzigdOp") else None
        ),
    }


def party_vote_from_dto(dto: StemmingDTO) -> dict[str, str]:
    return {"vote": dto.Soort}
