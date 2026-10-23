import pandas as pd
from django.core.management.base import OutputWrapper
from django.db.models import QuerySet
from analyzer.votes import party_votes
from scraper.models import Party, ParliamentaryItem
from typing import TextIO, MutableMapping, Any, Mapping, cast
import logging

logger = logging.getLogger(__name__)

# Minimum record coverage (in %, measured from each party's own start) for
# a party to be included in the analysis. Filters out parties that are not
# really active, e.g. a group that stopped voting.
PARTICIPATION_THRESHOLD: float = 90.0

# The PCA axes are fitted on the parties with a vote on at least this share
# of the motions (in practice: present the whole period). The other parties
# are projected onto those axes afterwards, using only the motions they
# voted on; see `analyzer.analysis.prepare_df`.
PCA_FIT_COVERAGE: float = 0.99

# A projected party needs at least this many votes on the fitted motions;
# below that its position is too uncertain to show. As W-NOMINATE's default.
PCA_MIN_PROJECTED_VOTES: int = 20


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


def party_vote_mapper(vote: str) -> float:
    """
    Map positions to numbers; recorded non-participation stays missing.
    """
    mapping = {"For": 1, "Against": -1, "Split": 0, "Abstain": float("nan")}
    return mapping[vote]


def generate_dataframe(log: AnalysisLogger) -> pd.DataFrame:
    """
    Load data from the database and return it as a pandas DataFrame.

    Since we skip ParliamentaryItems where Parties did not vote, only Parties
    with record coverage of at least PARTICIPATION_THRESHOLD are
    included in the DataFrame. This way, we ensure that the PCA analysis is
    not skewed by Parties that are not really active.
    """
    record_coverage_cutoff: float = PARTICIPATION_THRESHOLD

    included_parties = Party.objects.filter(
        record_coverage__gte=record_coverage_cutoff
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
        f"{excluded_count} {party_word} excluded from analysis due to low record coverage.",
        extra={
            "excluded_parties": excluded_names,
            "excluded_count": excluded_count,
            "cutoff": record_coverage_cutoff,
        },
    )

    items: QuerySet[ParliamentaryItem] = (
        ParliamentaryItem.objects.all().order_by("-date")
    )

    # Includes votes inherited from a predecessor party.
    votes = party_votes()
    vote_lookup: dict[tuple[int, int], str] = {
        (item_id, party.id): vote
        for party in included_parties
        for item_id, vote in votes.get(party.id, {}).items()
    }

    # Add row for each motion and fill in votes
    data = []
    for item in items:
        row: dict[str, str | float]
        row = {"Motion ID": item.id}
        for party in included_parties:
            vote = vote_lookup.get((item.id, party.id))
            if vote is not None:
                row[party.abbreviation] = party_vote_mapper(vote)
            else:
                log.info(
                    f"Party {party.abbreviation} did not vote for item: {item.id}",
                    extra={
                        "party_id": party.id,
                        "party": party.abbreviation,
                        "item_id": item.id,
                    },
                )
        data.append(row)

    df = pd.DataFrame(
        data,
        columns=["Motion ID"]
        + [party.abbreviation for party in included_parties],
    )
    return df
