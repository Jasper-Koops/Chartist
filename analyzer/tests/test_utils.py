from django.test import TestCase
import io

from analyzer.utils import (
    AnalysisLogger,
    generate_dataframe,
    log_to_stdout,
)
from scraper.models import Party, PartyVote, VoteType
from scraper.tests.factories import PartyFactory
from scraper.tests.utils.testing_utils import (
    generate_parties,
    generate_parliamentary_items,
    generate_party_votes,
)
import logging

logger = logging.getLogger(__name__)


class LogToStdoutTests(TestCase):
    def test_writes_to_provided_stdout(self) -> None:
        buffer = io.StringIO()
        log_to_stdout("hello world", stdout=buffer)

        self.assertEqual(buffer.getvalue(), "hello world")

    def test_prints_to_stdout_when_none(self) -> None:
        buffer = io.StringIO()

        # Patch sys.stdout temporarily
        import sys

        original_stdout = sys.stdout
        try:
            sys.stdout = buffer
            log_to_stdout("hello world")
        finally:
            sys.stdout = original_stdout

        self.assertEqual(buffer.getvalue().strip(), "hello world")


class TestAnalysisLogger(TestCase):
    def test_logger_contains_analysis_id(self) -> None:
        analysis_id = 42
        log = AnalysisLogger(logger, {"analysis_id": analysis_id})
        assert log.extra is not None
        extra_data = dict(log.extra)
        self.assertEqual(extra_data["analysis_id"], analysis_id)

    def test_new_extra_values_append(self) -> None:
        log = AnalysisLogger(logger, {"analysis_id": 42})

        with self.assertLogs(logger, level="INFO") as cm:
            log.info("new log", extra={"new_key": "new_value"})

        record = cm.records[0]
        assert hasattr(record, "new_key")
        assert hasattr(record, "analysis_id")

        self.assertEqual(record.analysis_id, 42)
        self.assertEqual(record.new_key, "new_value")


class TestGenerateDataFrame(TestCase):
    def setUp(self) -> None:
        self.parties = generate_parties().order_by("abbreviation")
        self.items = generate_parliamentary_items(5).order_by("-date")
        self.log = AnalysisLogger(logger, {})
        generate_party_votes(
            parliamentary_items=self.items, parties=self.parties
        )

    def test_non_participation_is_missing_and_split_is_zero(self) -> None:
        from analyzer.analysis import calculate_party_participation_rate

        party = self.parties.first()
        items = list(self.items)
        PartyVote.objects.filter(
            party=party, parliamentary_item=items[0]
        ).update(vote=VoteType.ABSTAIN)
        PartyVote.objects.filter(
            party=party, parliamentary_item=items[1]
        ).update(vote=VoteType.SPLIT)
        calculate_party_participation_rate()
        df = generate_dataframe(log=self.log).set_index("Motion ID")
        self.assertTrue(df.loc[[items[0].id], party.abbreviation].isna().all())
        self.assertEqual(0, df.loc[items[1].id, party.abbreviation])
        # A low participation percentage does not exclude the party.
        party.refresh_from_db()
        self.assertEqual(80.0, party.participation_rate)

    def test_function_generates_dataframe(self) -> None:
        df = generate_dataframe(log=self.log)

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
                    VoteType.SPLIT.value: 0,
                }
                expected_vote: int = vote_map[party_vote.vote]
                self.assertEqual(
                    df.iloc[index][party.abbreviation], expected_vote
                )


class TestPcaPartySelection(TestCase):
    def included(self) -> list[str]:
        return list(
            generate_dataframe(log=AnalysisLogger(logger, {})).columns[1:]
        )

    def test_participation_does_not_filter_parties(self) -> None:
        parties = [
            PartyFactory(participation_rate=rate)
            for rate in (None, 0, 50, 89, 100)
        ]
        self.assertCountEqual(
            [party.abbreviation for party in parties], self.included()
        )

    def test_predecessor_is_excluded_even_with_full_participation(self) -> None:
        from datetime import date
        from scraper.models import PartySuccession

        old = PartyFactory(participation_rate=100)
        successor = PartyFactory(participation_rate=50)
        PartySuccession.objects.create(
            predecessor=old,
            successor=successor,
            date=date(2026, 1, 1),
            member_overlap=1,
        )
        self.assertEqual([successor.abbreviation], self.included())

    def test_only_final_successor_in_chain_is_included(self) -> None:
        from datetime import date
        from scraper.models import PartySuccession

        old, middle, newest = [PartyFactory() for _ in range(3)]
        PartySuccession.objects.create(
            predecessor=old,
            successor=middle,
            date=date(2026, 1, 1),
            member_overlap=1,
        )
        PartySuccession.objects.create(
            predecessor=middle,
            successor=newest,
            date=date(2026, 2, 1),
            member_overlap=1,
        )
        self.assertEqual([newest.abbreviation], self.included())
