from datetime import date

import numpy as np
import pandas as pd
from django.db.transaction import atomic

from analyzer.models import AgreementMatrix, PartyAgreement
from analyzer.votes import item_vote_dates, lineage_pairs, party_votes
from scraper.models import VoteType


def load_vote_table() -> pd.DataFrame:
    """
    Load the FOR/AGAINST votes as a table of items (rows) by parties
    (columns), including inherited votes (see `party_votes`).

    Non-participation and evenly split positions are excluded, so a cell
    is FOR, AGAINST or empty.

    Returns:
        pd.DataFrame: Votes indexed by item id, with party ids as columns.
    """
    votes = pd.DataFrame(
        [
            (item_id, party_id, vote)
            for party_id, items in party_votes().items()
            for item_id, vote in items.items()
            if vote in (VoteType.FOR, VoteType.AGAINST)
        ],
        columns=["item", "party", "vote"],
    )
    if votes.empty:
        return pd.DataFrame()
    return votes.pivot(index="item", columns="party", values="vote")


def count_agreement(table: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Count shared and agreeing motions for every pair of parties in a table.

    Args:
        table (pd.DataFrame): Votes as returned by `load_vote_table`, or a
            subset of its rows.

    Returns:
        tuple: A tuple containing:
            - shared (np.ndarray): Number of shared motions per pair.
            - agreed (np.ndarray): Number of shared motions on which the pair
              voted the same.
    """
    voted_for = (table == VoteType.FOR).to_numpy(dtype=int)
    voted_against = (table == VoteType.AGAINST).to_numpy(dtype=int)
    voted = voted_for + voted_against
    shared = voted.T @ voted
    agreed = voted_for.T @ voted_for + voted_against.T @ voted_against
    return shared, agreed


def calculate_agreement() -> tuple[list[int], np.ndarray, np.ndarray]:
    """
    Calculate the pairwise voting agreement between all parties with votes.

    Two parties are compared on the motions on which both voted for or
    against. The agreement is the share of those motions on which they
    voted the same. Inherited votes count (see `party_votes`), so a party
    that continues another party is compared over its predecessor's history
    too.

    Returns:
        tuple: A tuple containing:
            - party_ids (list[int]): Party ids, in matrix order.
            - shared (np.ndarray): Number of shared motions per pair.
            - agreed (np.ndarray): Number of shared motions on which the pair
              voted the same.
    """
    table = load_vote_table()
    if table.empty:
        return [], np.zeros((0, 0)), np.zeros((0, 0))
    shared, agreed = count_agreement(table)
    return list(table.columns), shared, agreed


def item_months(item_ids: list[int]) -> dict[int, date]:
    """
    Map items to the first day of their voting month (see `item_vote_dates`).

    Args:
        item_ids (list[int]): The items to map.

    Returns:
        dict[int, date]: First day of the month per item id.
    """
    return {
        item_id: day.replace(day=1)
        for item_id, day in item_vote_dates(item_ids).items()
    }


def run_agreement_analysis() -> AgreementMatrix:
    """
    Calculate the agreement matrix and store it.

    Stores one row per ordered pair of different parties for the whole
    period (month empty), plus one row per pair per calendar month in which
    the pair shared at least one motion, for timelines.

    A party is not compared with its own predecessor or successor: with
    inherited votes they would trivially agree. Those pairs are stored
    without an agreement and with 0 shared motions, and get no monthly rows.

    Returns:
        AgreementMatrix: The stored matrix.
    """
    table = load_vote_table()
    party_ids: list[int] = list(table.columns)
    same_lineage = lineage_pairs()

    def rows(
        matrix: AgreementMatrix,
        shared: np.ndarray,
        agreed: np.ndarray,
        month: date | None,
    ) -> list[PartyAgreement]:
        result = []
        for i, party_id in enumerate(party_ids):
            for j, other_id in enumerate(party_ids):
                if i == j:
                    continue
                lineage = (party_id, other_id) in same_lineage
                n_shared = 0 if lineage else int(shared[i, j])
                if month is not None and n_shared == 0:
                    continue
                result.append(
                    PartyAgreement(
                        matrix=matrix,
                        party_id=party_id,
                        other_party_id=other_id,
                        month=month,
                        shared_motions=n_shared,
                        agreement=(
                            agreed[i, j] / n_shared if n_shared else None
                        ),
                    )
                )
        return result

    with atomic():
        matrix = AgreementMatrix.objects.create()
        if table.empty:
            return matrix
        agreements = rows(matrix, *count_agreement(table), month=None)
        months = item_months(list(table.index))
        by_month = table.index.map(months)
        for month, subset in table.groupby(by_month):
            agreements += rows(matrix, *count_agreement(subset), month=month)
        PartyAgreement.objects.bulk_create(agreements)
    return matrix
