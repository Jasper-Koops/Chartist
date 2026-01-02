from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Party(models.Model):
    """
    Mirrors the API 'factie' model
    """

    api_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name = "Party"
        verbose_name_plural = "Parties"

    def __str__(self) -> str:
        return self.name


class ParliamentaryItemTypes(models.TextChoices):
    MOTION = "Motion", "Motion"


class ParliamentaryItemStatusTypes(models.TextChoices):
    ACCEPTED = "Accepted", "Accepted"
    REJECTED = "Rejected", "Rejected"
    PENDING = "Pending", "Pending"


class ParliamentaryItem(models.Model):
    api_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    date = models.DateTimeField()
    item_type = models.CharField(
        max_length=20, choices=ParliamentaryItemTypes.choices
    )
    status = models.CharField(
        max_length=20,
        choices=ParliamentaryItemStatusTypes.choices,
        default=ParliamentaryItemStatusTypes.PENDING,
    )

    def __str__(self) -> str:
        return f"{self.item_type} - {self.title} - {self.status}"

    def clean(self) -> None:
        super().clean()
        if self.date and timezone.is_naive(self.date):
            raise ValidationError({"date": "Datetime must be timezone-aware."})


class VoteType(models.TextChoices):
    FOR = "For", "For"
    AGAINST = "Against", "Against"
    ABSTAIN = "Abstain", "Abstain"


class PartyVote(models.Model):
    party = models.ForeignKey(Party, on_delete=models.CASCADE)
    parliamentary_item = models.ForeignKey(
        ParliamentaryItem, on_delete=models.CASCADE
    )
    vote = models.CharField(max_length=10, choices=VoteType.choices)

    class Meta:
        unique_together = ("party", "parliamentary_item")

    def __str__(self) -> str:
        return (
            f"{self.party.name} - {self.parliamentary_item.title} - {self.vote}"
        )
