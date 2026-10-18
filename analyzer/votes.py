from collections import defaultdict
from collections.abc import Iterable
from datetime import date

from django.utils import timezone

from scraper.models import ParliamentaryItem, PartySuccession, PartyVote


def party_votes(
    party_ids: Iterable[int] | None = None,
) -> dict[int, dict[int, str]]:
    """
    Load the votes per party for the analysis, including inherited votes.

    A successor (see `PartySuccession`) inherits its predecessor's votes on
    items it did not vote on itself; its own votes always win. Chains are
    followed in date order, so in A -> B -> C, C also inherits A's votes.
    The predecessor keeps its own votes.

    Args:
        party_ids (Iterable[int] | None): Only load these parties (and,
            for inheritance, their predecessors); all parties if None. The
            result may contain the predecessors too.

    Returns:
        dict[int, dict[int, str]]: Votes keyed by party id, then item id.
    """
    successions = list(
        PartySuccession.objects.order_by("date").values_list(
            "predecessor_id", "successor_id"
        )
    )
    votes_query = PartyVote.objects.all()
    if party_ids is not None:
        # Add every predecessor in the chains of the requested parties.
        wanted = set(party_ids)
        predecessor_of = {
            successor: predecessor for predecessor, successor in successions
        }
        for party_id in list(wanted):
            while party_id in predecessor_of:
                party_id = predecessor_of[party_id]
                wanted.add(party_id)
        votes_query = votes_query.filter(party_id__in=wanted)

    votes: defaultdict[int, dict[int, str]] = defaultdict(dict)
    for item_id, party_id, vote in votes_query.values_list(
        "parliamentary_item_id", "party_id", "vote"
    ):
        votes[party_id][item_id] = vote

    for predecessor_id, successor_id in successions:
        if predecessor_id not in votes:
            continue
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


def item_vote_dates(item_ids: Iterable[int] | None = None) -> dict[int, date]:
    """
    The voting date of each item, for ordering items in time.

    Uses `vote_date`; falls back to the local date of the last modification
    (`date`) for an item without one.

    Args:
        item_ids (Iterable[int] | None): Items to include; all if None.

    Returns:
        dict[int, date]: Voting date per item id.
    """
    items = ParliamentaryItem.objects.all()
    if item_ids is not None:
        items = items.filter(id__in=list(item_ids))
    return {
        item_id: vote_date or timezone.localtime(modified).date()
        for item_id, vote_date, modified in items.values_list(
            "id", "vote_date", "date"
        )
    }
