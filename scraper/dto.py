from dataclasses import dataclass
from typing import Mapping, Any
from typeguard import typechecked
from datetime import datetime
from pydantic import BaseModel, ValidationError

from scraper.models import ParliamentaryItemStatusTypes, VoteType


class FractieInput(BaseModel):
    Id: str
    NaamNL: str
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
        Afkorting (str): Abbreviation of the party name.
        AantalZetels (int): Number of seats held by the party.
        AantalStemmen (int): Number of votes received by the party.
        DatumActief (datetime | None): Date when the party became active.
        DatumInactief (datetime | None): Date when the party became inactive.
    """

    Id: str
    NaamNL: str
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
            Afkorting=validated.Afkorting,
            AantalZetels=validated.AantalZetels,
            AantalStemmen=validated.AantalStemmen,
            DatumActief=validated.DatumActief,
            DatumInactief=validated.DatumInactief,
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


class BesluitInput(BaseModel):
    Id: str
    Agendapunt_Id: str
    BesluitSoort: str
    GewijzigdOp: datetime
    Stemming: list[Mapping[str, Any]]


@dataclass
@typechecked
class BesluitDTO:
    """
    Data Transfer Object (DTO) for a parliamentary decision (Besluit).

    Attributes:
        Id (str): Unique identifier of the decision.
        Agendapunt_Id (str): Identifier of the agenda point.
        BesluitSoort (ParliamentaryItemStatusTypes): Status of the decision.
        GewijzigdOp (datetime): Last modified date of the decision.
        Stemming (list[StemmingDTO]): List of associated votes.
    """

    Id: str
    Agendapunt_Id: str
    BesluitSoort: ParliamentaryItemStatusTypes
    GewijzigdOp: datetime
    Stemming: list[StemmingDTO]

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "BesluitDTO":
        """
        Create a BesluitDTO instance from API data.

        Args:
            data (BesluitInput): The API data containing decision information.

        Returns:
            BesluitDTO: An instance of BesluitDTO.

        Raises:
            ValueError: If any required field is missing or None.
        """
        try:
            validated = BesluitInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        return cls(
            Id=validated.Id,
            Agendapunt_Id=validated.Agendapunt_Id,
            BesluitSoort=cls.get_parliamentary_item_status(
                validated.BesluitSoort
            ),
            GewijzigdOp=validated.GewijzigdOp,
            Stemming=[StemmingDTO.from_api(s) for s in validated.Stemming],
        )

    @staticmethod
    def get_parliamentary_item_status(
        data: str,
    ) -> ParliamentaryItemStatusTypes:
        """
        Map a decision status string from the API to a
            ParliamentaryItemStatusTypes enum.

        The values provided by the API may not standardized. The function will
        clean and tokenize the values before comparing them. It will also
        check for negations to handle the inevitable 'Niet aangenomen' bug
        that I can see approaching from the horizon.

        Args:
            data (str): The decision status string from the API.

        Returns:
            ParliamentaryItemStatusTypes: The corresponding
                ParliamentaryItemStatusTypes enum value.

        Raises:
            ValueError: If the decision status is unknown.
        """
        negations: set[str] = {"niet"}
        value = data.strip().lower()

        # Normalize common punctuation into spaces so tokenization works.
        for ch in ".()[],:;-/":
            value = value.replace(ch, " ")

        tokens = value.split()

        # "niet aangenomen" is semantically equivalent to "verworpen".
        if {"niet", "aangenomen"}.issubset(tokens):
            return ParliamentaryItemStatusTypes.REJECTED

        # Detect remaining negations — the API is not to be trusted.
        if negations.intersection(tokens):
            raise ValueError(f"Negation detected in: {data}")

        # Exact match dictionary for known values
        status_mapping = {
            "aangenomen": ParliamentaryItemStatusTypes.ACCEPTED,
            "verworpen": ParliamentaryItemStatusTypes.REJECTED,
            "aangehouden": ParliamentaryItemStatusTypes.PENDING,
        }

        # Get status from values that include the votes ('Aangenomen 76-74')
        for keyword, status in status_mapping.items():
            if keyword in tokens:
                return status

        raise ValueError(f"Unknown parliamentary item status: {data}")


class ZaakBesluitInput(BaseModel):
    Id: str
    Onderwerp: str
    Vergaderjaar: str
    GestartOp: datetime
    GewijzigdOp: datetime
    Besluit: list[Mapping[str, Any]]
    Document: list[Mapping[str, Any]]


@dataclass
@typechecked
class ZaakBesluitDTO:
    """
    Data Transfer Object (DTO) for a Zaak with nested Besluit and Document.

    Attributes:
        Id (str): Unique identifier of the Zaak.
        Onderwerp (str): Subject of the Zaak.
        GestartOp (datetime): Start date of the Zaak.
        GewijzigdOp (datetime): Last modified date of the Zaak.
        Besluit (list[BesluitDTO]): List of associated decisions.
        Document (list[dict]): List of associated documents.
    """

    Id: str
    Onderwerp: str
    Vergaderjaar: str
    GestartOp: datetime
    GewijzigdOp: datetime
    Besluit: list[BesluitDTO]
    Document: list[dict[str, Any]]

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "ZaakBesluitDTO":
        """
        Create a ZaakBesluitDTO instance from API data.

        Args:
            data (ZaakBesluitInput): The API data containing Zaak, Besluit,
            and Document information.

        Returns:
            ZaakBesluitDTO: An instance of ZaakBesluitDTO.

        Raises:
            ValueError: If any required field is missing or None, or if
            Besluit is empty.
        """
        try:
            validated = ZaakBesluitInput.model_validate(data)
        except ValidationError as e:
            raise ValueError(str(e)) from e

        if not validated.Besluit:
            raise ValueError("Expected at least one Besluit, got 0")

        return cls(
            Id=validated.Id,
            Onderwerp=validated.Onderwerp,
            Vergaderjaar=validated.Vergaderjaar,
            GestartOp=validated.GestartOp,
            GewijzigdOp=validated.GewijzigdOp,
            Besluit=[BesluitDTO.from_api(b) for b in validated.Besluit],
            Document=[dict(d) for d in validated.Document],
        )
