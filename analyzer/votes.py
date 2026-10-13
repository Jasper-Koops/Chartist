from collections import defaultdict

from scraper.models import PartySuccession, PartyVote


def party_votes() -> dict[int, dict[int, str]]:
    """
    Load the votes per party for the analysis, including inherited votes.

    A successor (see `PartySuccession`) inherits its predecessor's votes on
    items it did not vote on itself; its own votes always win. Chains are
    followed in date order, so in A -> B -> C, C also inherits A's votes.
    The predecessor keeps its own votes.

    Returns:
        dict[int, dict[int, str]]: Votes keyed by party id, then item id.
    """
    votes: defaultdict[int, dict[int, str]] = defaultdict(dict)
    for item_id, party_id, vote in PartyVote.objects.values_list(
        "parliamentary_item_id", "party_id", "vote"
    ):
        votes[party_id][item_id] = vote

    for predecessor_id, successor_id in PartySuccession.objects.order_by(
        "date"
    ).values_list("predecessor_id", "successor_id"):
        successor_votes = votes[successor_id]
        for item_id, vote in votes[predecessor_id].items():
            successor_votes.setdefault(item_id, vote)

    return dict(votes)


def lineage_pairs() -> set[tuple[int, int]]:
    """
    Pairs of parties in the same succession chain, in both orders.

    Returns:
        set[tuple[int, int]]: (party id, other party id) pairs.
    """
    successor_of = dict(
        PartySuccession.objects.values_list("predecessor_id", "successor_id")
    )
    pairs: set[tuple[int, int]] = set()
    for start in successor_of:
        current = start
        while current in successor_of:
            current = successor_of[current]
            pairs.add((start, current))
            pairs.add((current, start))
    return pairs
