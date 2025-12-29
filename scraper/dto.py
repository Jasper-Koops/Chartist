from dataclasses import dataclass
from typing import Mapping, Any
from typeguard import typechecked
from datetime import datetime
from pydantic import BaseModel, ValidationError

from scraper.models import ParliamentaryItemStatusTypes, VoteType


class FractieInput(BaseModel):
    Id: str
    NaamNL: str
    NaamEN: str
    Afkorting: str
    AantalZetels: int
    AantalStemmen: int
    DatumActief: datetime
    DatumInactief: datetime | None


@dataclass
@typechecked
class FractieDTO:
    """
    Data Transfer Object (DTO) for a political party (Fractie).

    Attributes:
        Id (str): Unique identifier of the party.
        NaamNL (str): Name of the party in Dutch.
        NaamEN (str): Name of the party in English.
        Afkorting (str): Abbreviation of the party name.
        AantalZetels (int): Number of seats held by the party.
        AantalStemmen (int): Number of votes received by the party.
        DatumActief (datetime | None): Date when the party became active.
        DatumInactief (datetime | None): Date when the party became inactive.
    """

    Id: str
    NaamNL: str
    NaamEN: str
    Afkorting: str
    AantalZetels: int
    AantalStemmen: int
    DatumActief: datetime | None
    DatumInactief: datetime | None

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "FractieDTO":
        """
        Create a FractieDTO instance from API data.

        Args:
            data (FractieInput): The API data containing party information.

        Returns:
            FractieDTO: An instance of FractieDTO.

        Raises:
            ValueError: If any required field is missing or None.
        """
        try:
            validated = FractieInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        return cls(
            Id=validated.Id,
            NaamNL=validated.NaamNL,
            NaamEN=validated.NaamEN,
            Afkorting=validated.Afkorting,
            AantalZetels=validated.AantalZetels,
            AantalStemmen=validated.AantalStemmen,
            DatumActief=validated.DatumActief,
            DatumInactief=validated.DatumInactief,
        )


class ZaakInput(BaseModel):
    Id: str
    Soort: str
    Titel: str
    Onderwerp: str
    Vergaderjaar: str
    GestartOp: datetime
    GewijzigdOp: datetime


@dataclass
@typechecked
class ZaakDTO:
    """
    Data Transfer Object (DTO) for a parliamentary item (Zaak).

    Attributes:
        Id (str): Unique identifier of the item.
        Soort (str): Type of the item.
        Titel (str): Title of the item.
        Onderwerp (str): Subject of the item.
        Vergaderjaar (str): Parliamentary year of the item.
        GestartOp (datetime): Start date of the item.
        GewijzigdOp (datetime): Last modified date of the item.
    """

    Id: str
    Soort: str
    Titel: str
    Onderwerp: str
    Vergaderjaar: str
    GestartOp: datetime
    GewijzigdOp: datetime

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ZaakDTO":
        """
        Create a ZaakDTO instance from API data.

        Args:
            data (ZaakInput): The API data containing item information.

        Returns:
            ZaakDTO: An instance of ZaakDTO.

        Raises:
            ValueError: If any required field is missing or None.
        """
        try:
            validated = ZaakInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        return cls(
            Id=validated.Id,
            Soort=validated.Soort,
            Titel=validated.Titel,
            Onderwerp=validated.Onderwerp,
            Vergaderjaar=validated.Vergaderjaar,
            GestartOp=validated.GestartOp,
            GewijzigdOp=validated.GewijzigdOp,
        )


class StemmingInput(BaseModel):
    Soort: str
    Fractie_Id: str


@dataclass
@typechecked
class StemmingDTO:
    """
    Data Transfer Object (DTO) for a vote (Stemming).

    Attributes:
        Soort (str): Type of the vote.
        Fractie_Id (str): Identifier of the party associated with the vote.
    """

    Soort: str
    Fractie_Id: str

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "StemmingDTO":
        """
        Create a StemmingDTO instance from API data.

        Args:
            data (StemmingInput): The API data containing vote information.

        Returns:
            StemmingDTO: An instance of StemmingDTO.

        Raises:
            ValueError: If any required field is missing or None.
        """
        try:
            validated = StemmingInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        return cls(
            Soort=cls.get_party_vote_type(validated.Soort),
            Fractie_Id=validated.Fractie_Id,
        )

    @staticmethod
    def get_party_vote_type(vote_data: str) -> VoteType:
        """
        Map a vote type string from the API to a VoteType enum.

        Args:
            vote_data (str): The vote type string from the API.

        Returns:
            VoteType: The corresponding VoteType enum value.

        Raises:
            ValueError: If the vote type is unknown.
        """
        vote_mapping: dict[str, VoteType] = {
            "voor": VoteType.FOR,
            "tegen": VoteType.AGAINST,
            "niet deelgenomen": VoteType.ABSTAIN,
        }
        value: str = vote_data.strip().lower().rstrip(".")
        result = vote_mapping.get(value)
        if result is None:
            raise ValueError(f"Unknown vote type: {vote_data}")
        return result


class AgendapuntZaakBesluitVolgordeInput(BaseModel):
    Id: str
    Agendapunt_Id: str
    BesluitSoort: str
    BesluitTekst: str
    GewijzigdOp: datetime
    Zaak: list[Mapping[str, Any]]
    Stemming: list[Mapping[str, Any]]


@dataclass
@typechecked
class AgendapuntZaakBesluitVolgordeDTO:
    """
    Data Transfer Object (DTO) for an agenda item, item, and decision sequence.

    Attributes:
        Id (str): Unique identifier of the agenda item.
        Agendapunt_Id (str): Identifier of the agenda point.
        BesluitSoort (str): Type of the decision.
        BesluitTekst (str): Text describing the decision.
        GewijzigdOp (datetime): Last modified date of the decision.
        Zaak (list[ZaakDTO]): List of associated items.
        Stemming (list[StemmingDTO]): List of associated votes.
    """

    Id: str
    Agendapunt_Id: str
    BesluitSoort: str
    BesluitTekst: str
    GewijzigdOp: datetime
    Zaak: list[ZaakDTO]
    Stemming: list[StemmingDTO]

    @classmethod
    def from_api(
        cls, data: Mapping[str, Any]
    ) -> "AgendapuntZaakBesluitVolgordeDTO":
        """
        Create an AgendapuntZaakBesluitVolgordeDTO instance from API data.

        Args:
            data (AgendapuntZaakBesluitVolgordeInput): The API data containing agenda item, item, and
            decision information.

        Returns:
            AgendapuntZaakBesluitVolgordeDTO: An instance of
            AgendapuntZaakBesluitVolgordeDTO.

        Raises:
            ValueError: If any required field is missing or None, or if there
            is not exactly one item.
        """
        try:
            validated = AgendapuntZaakBesluitVolgordeInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        if len(data["Zaak"]) != 1:
            raise ValueError(
                f"Expected one, got {len(data['Zaak'])} Zaak items"
            )

        return cls(
            Id=validated.Id,
            Agendapunt_Id=validated.Agendapunt_Id,
            BesluitSoort=validated.BesluitSoort,
            BesluitTekst=cls.get_parliamentary_item_status(
                validated.BesluitTekst
            ),
            GewijzigdOp=validated.GewijzigdOp,
            Zaak=[ZaakDTO.from_api(zaak) for zaak in validated.Zaak],
            Stemming=[
                StemmingDTO.from_api(vote) for vote in validated.Stemming
            ],
        )

    @staticmethod
    def get_parliamentary_item_status(
        data: str,
    ) -> ParliamentaryItemStatusTypes:
        """
        Map a decision status string from the API to a
            ParliamentaryItemStatusTypes enum.

        Args:
            data (str): The decision status string from the API.

        Returns:
            ParliamentaryItemStatusTypes: The corresponding
                ParliamentaryItemStatusTypes enum value.

        Raises:
            ValueError: If the decision status is unknown.
        """
        value = data.strip().lower().rstrip(".")

        # Exact match dictionary for known values
        status_mapping = {
            "aangenomen": ParliamentaryItemStatusTypes.ACCEPTED,
            "verworpen": ParliamentaryItemStatusTypes.REJECTED,
            "aangehouden": ParliamentaryItemStatusTypes.PENDING,
        }

        # Try exact match first
        result = status_mapping.get(value)
        if result is None:
            raise ValueError(f"Unknown parliamentary item status: {data}")

        return result
