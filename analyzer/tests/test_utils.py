from django.test import TestCase
import io

from analyzer.utils import (
    PARTICIPATION_THRESHOLD,
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
                    VoteType.ABSTAIN.value: 0,
                }
                expected_vote: int = vote_map[party_vote.vote]
                self.assertEqual(
                    df.iloc[index][party.abbreviation], expected_vote
                )


class TestParticipationThreshold(TestCase):
    def setUp(self) -> None:
        self.log = AnalysisLogger(logger, {})

    def party(self, rate: float) -> Party:
        party: Party = PartyFactory(participation_rate=rate)
        return party

    def included(self) -> list[str]:
        return list(generate_dataframe(log=self.log).columns[1:])

    def test_party_missing_a_single_vote_is_included(self) -> None:
        # Under the old IQR rule, all parties at 100% made the cutoff 100%.
        full = [self.party(100.0) for _ in range(5)]
        almost = self.party(99.9)
        included = self.included()
        self.assertIn(almost.abbreviation, included)
        for party in full:
            self.assertIn(party.abbreviation, included)

    def test_threshold_is_inclusive(self) -> None:
        party = self.party(PARTICIPATION_THRESHOLD)
        self.assertIn(party.abbreviation, self.included())

    def test_party_below_threshold_is_excluded(self) -> None:
        self.party(100.0)
        inactive = self.party(PARTICIPATION_THRESHOLD - 0.1)
        self.assertNotIn(inactive.abbreviation, self.included())
