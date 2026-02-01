import pandas as pd
from django.core.management.base import OutputWrapper
from django.db.models import QuerySet
import statistics
from scraper.models import Party, PartyVote, ParliamentaryItem
from typing import List, TextIO, MutableMapping, Any, Mapping, cast
import logging


logger = logging.getLogger(__name__)


class AnalysisLogger(logging.LoggerAdapter[logging.Logger]):
    def process(
        self,
        msg: str,
        kwargs: MutableMapping[str, Any],
    ) -> tuple[str, MutableMapping[str, Any]]:
        kwargs.setdefault("extra", {})
        extra = kwargs["extra"]

        if isinstance(extra, dict):
            adapter_extra = self.extra
            if adapter_extra is not None:
                extra.update(cast(Mapping[str, Any], adapter_extra))

        return msg, kwargs


def log_to_stdout(
    msg: str, stdout: TextIO | OutputWrapper | None = None
) -> None:
    """
    Simple function to make sure logging messages are printed to stdout for
    terminal commands.
    """
    if stdout:
        stdout.write(msg)
    else:
        print(msg)


def party_vote_mapper(vote: str) -> int:
    """
    Map party vote strings to integers
    """
    mapping = {"For": 1, "Against": -1, "Abstain": 0}
    return mapping.get(vote, 0)


def generate_dataframe(log: AnalysisLogger) -> pd.DataFrame:
    """
    Load data from the database and return it as a pandas DataFrame.

    Since we skip ParliamentaryItems where Parties did not vote, we use
    the IQR method to determine a participation cutoff threshold for Parties.
    Only Parties with a participation rate above this threshold are included
    in the DataFrame. This way, we ensure that the PCA analysis is not skewed
    by Parties with very low participation rates.
    """
    # Use IQR to determine participation cutoff threshold
    participation_rates: List[float] = list(
        Party.objects.values_list(
            "participation_rate", flat=True  # type: ignore[arg-type]
        )
    )
    q1, _, q3 = statistics.quantiles(
        participation_rates, n=4, method="inclusive"
    )
    iqr: float = q3 - q1
    party_participation_cutoff_threshold: float = q1 - 1.5 * iqr

    included_parties = Party.objects.filter(
        participation_rate__gte=party_participation_cutoff_threshold
    ).order_by("abbreviation")

    excluded_parties = Party.objects.exclude(
        id__in=included_parties.values_list("id", flat=True)
    ).order_by("abbreviation")
    excluded_names = list(
        excluded_parties.values_list("abbreviation", flat=True)
    )
    excluded_count = len(excluded_names)
    party_word = "party" if excluded_count == 1 else "parties"
    log.info(
        f"{excluded_count} {party_word} excluded from analysis due to low participation rate.",
        extra={
            "excluded_parties": excluded_names,
            "excluded_count": excluded_count,
            "cutoff": party_participation_cutoff_threshold,
        },
    )

    items: QuerySet[
        ParliamentaryItem
    ] = ParliamentaryItem.objects.all().order_by("-date")

    # Add row for each motion and fill in votes
    data = []
    for item in items:
        row: dict[str, str | int]
        row = {"Motion ID": item.id}
        for party in included_parties:
            try:
                party_vote = PartyVote.objects.get(
                    parliamentary_item=item, party=party
                )
                row[party.abbreviation] = party_vote_mapper(party_vote.vote)
            except PartyVote.DoesNotExist:
                log.info(
                    f"Party {party.abbreviation} did not vote for item: {item.id}",
                    extra={
                        "party_id": party.id,
                        "party": {party.abbreviation},
                        "item_id": item.id,
                    },
                )
                continue
        data.append(row)

    df = pd.DataFrame(
        data,
        columns=["Motion ID"]
        + [party.abbreviation for party in included_parties],
    )
    return df
