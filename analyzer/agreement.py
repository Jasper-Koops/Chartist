import numpy as np
import pandas as pd
from django.db.transaction import atomic

from analyzer.models import AgreementMatrix, PartyAgreement
from analyzer.votes import lineage_pairs, party_votes
from scraper.models import VoteType


def calculate_agreement() -> tuple[list[int], np.ndarray, np.ndarray]:
    """
    Calculate the pairwise voting agreement between all parties with votes.

    Two parties are compared on the motions on which both voted for or
    against; 'Niet deelgenomen' (stored as abstain) is not a vote. The
    agreement is the share of those motions on which they voted the same.

    Inherited votes count (see `party_votes`), so a party that continues
    another party is compared over its predecessor's history too.

    Returns:
        tuple: A tuple containing:
            - party_ids (list[int]): Party ids, in matrix order.
            - shared (np.ndarray): Number of shared motions per pair.
            - agreed (np.ndarray): Number of shared motions on which the pair
              voted the same.
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
        return [], np.zeros((0, 0)), np.zeros((0, 0))

    table = votes.pivot(index="item", columns="party", values="vote")
    voted_for = (table == VoteType.FOR).to_numpy(dtype=int)
    voted_against = (table == VoteType.AGAINST).to_numpy(dtype=int)
    voted = voted_for + voted_against

    shared = voted.T @ voted
    agreed = voted_for.T @ voted_for + voted_against.T @ voted_against
    return list(table.columns), shared, agreed


def run_agreement_analysis() -> AgreementMatrix:
    """
    Calculate the agreement matrix and store it.

    A party is not compared with its own predecessor or successor: with
    inherited votes they would trivially agree. Those pairs are stored
    without an agreement and with 0 shared motions.

    Returns:
        AgreementMatrix: The stored matrix with one PartyAgreement per
            ordered pair of different parties.
    """
    party_ids, shared, agreed = calculate_agreement()
    same_lineage = lineage_pairs()
    with atomic():
        matrix = AgreementMatrix.objects.create()
        agreements = []
        for i, party_id in enumerate(party_ids):
            for j, other_id in enumerate(party_ids):
                if i == j:
                    continue
                n_shared = (
                    0
                    if (party_id, other_id) in same_lineage
                    else int(shared[i, j])
                )
                agreements.append(
                    PartyAgreement(
                        matrix=matrix,
                        party_id=party_id,
                        other_party_id=other_id,
                        shared_motions=n_shared,
                        agreement=(
                            agreed[i, j] / n_shared if n_shared else None
                        ),
                    )
                )
        PartyAgreement.objects.bulk_create(agreements)
    return matrix
