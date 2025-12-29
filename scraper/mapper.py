from datetime import datetime
from scraper.dto import (
    FractieDTO,
    AgendapuntZaakBesluitVolgordeDTO,
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
    dto: AgendapuntZaakBesluitVolgordeDTO,
) -> dict[str, str | datetime]:
    zaak_dto = dto.Zaak[0]
    return {
        "api_id": zaak_dto.Id,
        "title": zaak_dto.Onderwerp,
        "date": zaak_dto.GewijzigdOp,
        "item_type": ParliamentaryItemType.MOTION,
        "status": dto.BesluitTekst,
    }


def party_vote_from_dto(dto: StemmingDTO) -> dict[str, str]:
    return {"vote": dto.Soort}
