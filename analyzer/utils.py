import pandas as pd
from django.core.management.base import OutputWrapper
from django.db.models import QuerySet
from analyzer.votes import party_votes
from scraper.models import Party, ParliamentaryItem
from typing import TextIO, MutableMapping, Any, Mapping, cast
import logging

logger = logging.getLogger(__name__)

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

    Parties with a recorded successor are represented by that successor.
    Their votes remain available through inheritance. Incomplete histories
    are handled by the fitting and projection rules in prepare_df.
    """
    included_parties = Party.objects.filter(succession__isnull=True).order_by(
        "abbreviation"
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
