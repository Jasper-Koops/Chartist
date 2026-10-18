from dataclasses import dataclass

from analyzer.votes import lineage_pairs, party_votes
from scraper.models import PartyVote, VoteType

VOTED = (VoteType.FOR, VoteType.AGAINST)

# Which items to list for a pair of parties.
RELATIONS = ("differed", "agreed", "all")


@dataclass
class PairSummary:
    """
    How two parties voted relative to each other.

    Attributes:
        shared_motions (int): Motions on which both voted for or against.
        agreed (int): Shared motions on which they voted the same.
        party_for_other_against (int): Shared motions where the first party
            voted for and the other against.
        party_against_other_for (int): The reverse.
        same_lineage (bool): The parties are a predecessor and successor;
            they are compared on their own votes only.
    """

    shared_motions: int
    agreed: int
    party_for_other_against: int
    party_against_other_for: int
    same_lineage: bool

    @property
    def agreement(self) -> float | None:
        return (
            self.agreed / self.shared_motions if self.shared_motions else None
        )


def pair_votes(
    party_id: int, other_id: int
) -> tuple[dict[int, str], dict[int, str], bool]:
    """
    The votes of two parties per item, as used by the agreement matrix.

    Inherited votes count (see `party_votes`), except between a party and
    its own predecessor or successor: those would trivially agree, so they
    are compared on their own recorded votes.

    Returns:
        tuple: Votes of the party and of the other party, keyed by item id,
            and whether the two are in the same succession chain.
    """
    if (party_id, other_id) in lineage_pairs():
        own: dict[int, dict[int, str]] = {party_id: {}, other_id: {}}
        for item_id, voter_id, vote in PartyVote.objects.filter(
            party_id__in=[party_id, other_id]
        ).values_list("parliamentary_item_id", "party_id", "vote"):
            own[voter_id][item_id] = vote
        return own[party_id], own[other_id], True
    votes = party_votes()
    return votes.get(party_id, {}), votes.get(other_id, {}), False


def summarize(
    votes: dict[int, str], other_votes: dict[int, str], same_lineage: bool
) -> PairSummary:
    """Count shared, agreeing and opposite votes of two parties."""
    shared = agreed = for_against = against_for = 0
    for item_id, vote in votes.items():
        other = other_votes.get(item_id)
        if vote not in VOTED or other not in VOTED:
            continue
        shared += 1
        if vote == other:
            agreed += 1
        elif vote == VoteType.FOR:
            for_against += 1
        else:
            against_for += 1
    return PairSummary(shared, agreed, for_against, against_for, same_lineage)


def related_items(
    votes: dict[int, str], other_votes: dict[int, str], relation: str
) -> list[int]:
    """
    Items on which two parties voted in the given relation.

    Args:
        votes (dict[int, str]): Votes of the first party per item.
        other_votes (dict[int, str]): Votes of the other party per item.
        relation (str): "differed" (one for, one against), "agreed" (both
            for or both against), or "all" (both have a recorded vote,
            including not taking part).

    Returns:
        list[int]: The item ids.
    """
    if relation not in RELATIONS:
        raise ValueError(f"Unknown relation: {relation}")
    items = []
    for item_id, vote in votes.items():
        other = other_votes.get(item_id)
        if other is None:
            continue
        both_voted = vote in VOTED and other in VOTED
        if (
            relation == "all"
            or (relation == "agreed" and both_voted and vote == other)
            or (relation == "differed" and both_voted and vote != other)
        ):
            items.append(item_id)
    return items
