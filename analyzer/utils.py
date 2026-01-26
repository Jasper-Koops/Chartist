import pandas as pd
from django.db.models import QuerySet

from scraper.models import Party, PartyVote, ParliamentaryItem


def party_vote_mapper(vote: str) -> int:
    """
    Map party vote strings to integers
    """
    mapping = {"For": 1, "Against": -1, "Abstain": 0}
    return mapping.get(vote, 0)


def generate_dataframe() -> pd.DataFrame:
    """
    Load data from the database and return it as a pandas DataFrame
    """
    parties: QuerySet[Party] = Party.objects.all().order_by("abbreviation")
    items: QuerySet[
        ParliamentaryItem
    ] = ParliamentaryItem.objects.all().order_by("-date")

    # Add row for each motion and fill in votes
    data = []
    for item in items:
        row: dict[str, str | int]
        row = {"Motion ID": item.id}
        for party in parties:
            try:
                party_vote = PartyVote.objects.get(
                    parliamentary_item=item, party=party
                )
                row[party.abbreviation] = party_vote_mapper(party_vote.vote)
            except PartyVote.DoesNotExist:
                print(
                    f"\n\nparlimentary_item: {item} - {item.id}, party: {party} - {party.id}\n\n"
                )
                raise ValueError("FAAL")
        data.append(row)

    df = pd.DataFrame(
        data,
        columns=["Motion ID"] + [party.abbreviation for party in parties],
    )
    return df
