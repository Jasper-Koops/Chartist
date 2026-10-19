from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from scraper.text import motion_core


class Party(models.Model):
    """
    Mirrors the API 'factie' model
    """

    api_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=10, unique=True)
    participation_rate = models.FloatField(
        help_text=_(
            "Participation rate in parliamentary votes as a percentage."
        ),
        blank=True,
        null=True,
    )

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
    title = models.TextField()
    # Last modified timestamp of the decision; changes when the record is
    # edited, e.g. when votes are published. Use vote_date for timelines.
    date = models.DateTimeField()
    vote_date = models.DateField(
        blank=True,
        null=True,
        help_text=_("Date of the voting session."),
    )
    item_type = models.CharField(
        max_length=20, choices=ParliamentaryItemTypes.choices
    )
    status = models.CharField(
        max_length=20,
        choices=ParliamentaryItemStatusTypes.choices,
        default=ParliamentaryItemStatusTypes.PENDING,
    )
    text = models.JSONField(blank=True, null=True)
    document_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text=_(
            "Identifier of the motion document on officielebekendmakingen.nl, "
            "e.g. 'kst-36848-53'."
        ),
    )

    def __str__(self) -> str:
        return f"{self.item_type} - {self.title} - {self.status}"

    @property
    def core_text(self) -> list[str]:
        """
        What the motion says, without the formula around it (see
        `scraper.text.motion_core`); `text` holds the full text.
        """
        return motion_core(self.text or [])

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


class PartyAlias(models.Model):
    """
    An older API id under which the API still records votes for a party.

    Example: 50PLUS was registered again after the 2025 election (new id),
    but its votes still reference its old, inactive record. The party keeps
    the current id; the old one becomes an alias, so the votes link to it.
    Detected during the import (see `ParliamentApi.import_parties` and
    `ParliamentApi.import_votes`) and correctable in the admin.
    """

    api_id = models.CharField(max_length=50, unique=True)
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="aliases"
    )

    class Meta:
        verbose_name = "Party Alias"
        verbose_name_plural = "Party Aliases"

    def __str__(self) -> str:
        return f"{self.api_id} -> {self.party}"


class PartySuccession(models.Model):
    """
    A party that continues another party under a new identity, e.g. a rename
    such as GroenLinks-PvdA -> PRO. Splits and mergers are not successions.

    Detected during the import (see `ParliamentApi.import_successions`) and
    correctable in the admin. In the analysis, the successor inherits the
    predecessor's votes; both parties stay visible.
    """

    predecessor = models.OneToOneField(
        Party, on_delete=models.CASCADE, related_name="succession"
    )
    successor = models.OneToOneField(
        Party, on_delete=models.CASCADE, related_name="predecession"
    )
    date = models.DateField(help_text=_("Date the successor became active."))
    member_overlap = models.FloatField(
        help_text=_(
            "Lowest share of members shared by both parties around the "
            "succession date: of the predecessor's last and of the "
            "successor's first members."
        )
    )

    class Meta:
        verbose_name = "Party Succession"
        verbose_name_plural = "Party Successions"

    def __str__(self) -> str:
        return f"{self.predecessor} -> {self.successor} ({self.date})"


class ImportRunStatus(models.TextChoices):
    RUNNING = "Running", "Running"
    SUCCEEDED = "Succeeded", "Succeeded"
    FAILED = "Failed", "Failed"


class ImportRun(models.Model):
    """
    One sync with the Parliament API: when it ran, how it ended and what it
    changed. Written by `scraper.utils.run_import`, which both the
    import_data command and the scheduled Celery task use.
    """

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=10,
        choices=ImportRunStatus.choices,
        default=ImportRunStatus.RUNNING,
    )
    error = models.TextField(blank=True, default="")
    motions = models.IntegerField(default=0)
    created = models.IntegerField(default=0)
    votes_created = models.IntegerField(default=0)
    votes_updated = models.IntegerField(default=0)
    votes_deleted = models.IntegerField(default=0)
    stale = models.IntegerField(default=0)
    texts_fetched = models.IntegerField(default=0)
    texts_failed = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Import Run"
        verbose_name_plural = "Import Runs"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Import {self.started_at:%Y-%m-%d %H:%M} ({self.status})"
