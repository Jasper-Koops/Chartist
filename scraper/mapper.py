from datetime import datetime
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
) -> dict[str, str | datetime]:
    return {
        "api_id": dto.Id,
        "title": dto.Onderwerp,
        "date": dto.Besluit[0].GewijzigdOp,
        "item_type": ParliamentaryItemType.MOTION,
        "status": dto.Besluit[0].BesluitSoort,
    }


def party_vote_from_dto(dto: StemmingDTO) -> dict[str, str]:
    return {"vote": dto.Soort}
