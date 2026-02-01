from unittest import mock

from django.test import TestCase
from scraper.tests.utils.testing_utils import (
    generate_parties,
    generate_parliamentary_items,
    generate_party_votes,
)
from scraper.tests.fixtures.utils_fixtures import PARTIES
from scraper.models import Party


class TestGenerateParties(TestCase):
    def test_generate_parties_creates_all(self) -> None:
        self.assertEqual(Party.objects.count(), 0)
        generate_parties()

        # After: expect len(PARTIES) parties created
        self.assertEqual(Party.objects.count(), len(PARTIES))

        # Verify every party in dict exists with correct values
        for abbreviation, name in PARTIES.items():
            party = Party.objects.get(abbreviation=abbreviation)
            self.assertEqual(party.name, name)


class TestGenerateParliamentaryItems(TestCase):
    def test_generate_parliamentary_items(self) -> None:
        items = generate_parliamentary_items(count=5)
        self.assertEqual(len(items), 5)


class TestGeneratePartyVotes(TestCase):
    def setUp(self) -> None:
        self.parties = generate_parties()
        self.items = generate_parliamentary_items(5)

    def test_verify_calculate_participation_rate_called(self) -> None:
        with mock.patch(
            "scraper.tests.utils.testing_utils.calculate_party_participation_rate"
        ) as mocked_calculate:
            generate_party_votes(
                parliamentary_items=self.items, parties=self.parties
            )
            mocked_calculate.assert_called_once()

    def test_verify_calculate_participation_rate_not_called(self) -> None:
        with mock.patch(
            "scraper.tests.utils.testing_utils.calculate_party_participation_rate"
        ) as mocked_calculate:
            generate_party_votes(
                parliamentary_items=self.items,
                parties=self.parties,
                calculate_participation_rate=False,
            )
            mocked_calculate.assert_not_called()

    def test_generate_party_votes(self) -> None:
        generate_party_votes(
            parliamentary_items=self.items, parties=self.parties
        )

        # Verify that each item has votes for each party
        for item in self.items:
            self.assertEqual(item.partyvote_set.count(), len(PARTIES))

        # Verify that the item.status is set correctly
        for item in self.items:
            for_votes = item.partyvote_set.filter(vote="For").count()
            against_votes = item.partyvote_set.filter(vote="Against").count()

            # If more 'for' votes than 'against', status should be 'Passed'
            if for_votes > against_votes:
                self.assertEqual(item.status, "Passed")
            # If more 'against' votes than 'for', status should be 'Rejected'
            elif against_votes >= for_votes:
                self.assertEqual(item.status, "Rejected")
