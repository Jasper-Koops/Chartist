from django.db.models import QuerySet

from scraper.tests.factories import (
    PartyFactory,
    ParliamentaryItemFactory,
    PartyVoteFactory,
)
from analyzer.analysis import calculate_party_participation_rate
from scraper.models import (
    Party,
    VoteType,
    ParliamentaryItem,
    ParliamentaryItemStatusTypes,
)
from scraper.tests.fixtures.utils_fixtures import PARTIES
import random


def generate_parties() -> QuerySet[Party]:
    """Will generate 15 parties defined in PARTIES dict"""
    for abbreviation, name in PARTIES.items():
        PartyFactory(abbreviation=abbreviation, name=name)

    return Party.objects.all()


def generate_parliamentary_items(count: int = 5) -> QuerySet[ParliamentaryItem]:
    for _ in range(count):
        ParliamentaryItemFactory()
    return ParliamentaryItem.objects.all()


def generate_party_votes(
    parliamentary_items: QuerySet[ParliamentaryItem],
    parties: QuerySet[Party],
    calculate_participation_rate: bool = True,
) -> None:
    """
    Generate party votes for the given parliamentary items and parties.

    :param parliamentary_items: QuerySet[ParliamentaryItem]: The parliamentary items to
      generate votes for
    :param parties: QuerySet[Party]: The parties to generate votes for
    :param calculate_participation_rate: bool: Flag to indicate whether to
        calculate participation rates after generating votes
    :return:
    """
    item: ParliamentaryItem
    for item in parliamentary_items:
        party: Party
        for party in parties:
            PartyVoteFactory(
                parliamentary_item=item,
                party=party,
                vote=random.choice(
                    [VoteType.FOR, VoteType.AGAINST, VoteType.ABSTAIN]
                ),
            )

        # Set status based on votes
        for_votes = item.partyvote_set.filter(vote=VoteType.FOR).count()
        against_votes = item.partyvote_set.filter(vote=VoteType.AGAINST).count()
        if for_votes > against_votes:
            item.status = ParliamentaryItemStatusTypes.ACCEPTED
        elif against_votes >= for_votes:
            item.status = ParliamentaryItemStatusTypes.REJECTED

        item.save()

    if calculate_participation_rate:
        calculate_party_participation_rate()
