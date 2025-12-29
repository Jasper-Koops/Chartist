from django.db.models import QuerySet

from scraper.tests.factories import (
    PartyFactory,
    ParliamentaryItemFactory,
    PartyVoteFactory,
)
from scraper.models import Party, VoteType, ParliamentaryItem
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
    parliamentary_items: QuerySet[ParliamentaryItem], parties: QuerySet[Party]
) -> None:

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
            item.status = "Passed"
        elif against_votes >= for_votes:
            item.status = "Rejected"

        item.save()
