from django.test import TestCase

from analyzer.utils import generate_dataframe
from scraper.models import PartyVote, VoteType
from scraper.tests.utils.testing_utils import (
    generate_parties,
    generate_parliamentary_items,
    generate_party_votes,
)


class TestGenerateDataFrame(TestCase):
    def setUp(self) -> None:
        self.parties = generate_parties().order_by("abbreviation")
        self.items = generate_parliamentary_items(5).order_by("-date")
        generate_party_votes(
            parliamentary_items=self.items, parties=self.parties
        )

    def test_function_generates_dataframe(self) -> None:
        df = generate_dataframe()

        # Check that the dataframe has the correct shape
        # Number of rows should equal number of items
        self.assertEqual(df.shape[0], len(self.items))
        # Number of columns should equal number of parties + 1 for motion title
        self.assertEqual(df.shape[1], len(self.parties) + 1)

        # Check that the columns are correct
        expected_columns = ["Motion ID"] + [
            party.abbreviation
            for party in self.parties.order_by("abbreviation")
        ]
        self.assertListEqual(list(df.columns), expected_columns)

        # Check that the data in the dataframe matches the votes in the database
        for index, item in enumerate(self.items):
            self.assertEqual(df.iloc[index]["Motion ID"], item.id)
            for party in self.parties:
                party_vote = PartyVote.objects.get(
                    parliamentary_item=item, party=party
                )

                vote_map: dict[str, int] = {
                    VoteType.FOR.value: 1,
                    VoteType.AGAINST.value: -1,
                    VoteType.ABSTAIN.value: 0,
                }
                expected_vote: int = vote_map[party_vote.vote]
                self.assertEqual(
                    df.iloc[index][party.abbreviation], expected_vote
                )
