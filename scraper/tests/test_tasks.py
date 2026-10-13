from unittest import mock

from django.test import TestCase

from Chartist.celery import app
from scraper import tasks
from scraper.utils import VoteImportResult


class TestTasks(TestCase):
    def setUp(self) -> None:
        # Run chained tasks in-process instead of sending them to the broker.
        app.conf.task_always_eager = True
        self.addCleanup(setattr, app.conf, "task_always_eager", False)

    def mock_import(self, result: VoteImportResult) -> mock.Mock:
        patcher = mock.patch.object(tasks, "ParliamentApi")
        api_class = patcher.start()
        self.addCleanup(patcher.stop)
        api_class.return_value.import_votes.return_value = result
        return api_class

    def mock_analysis(self) -> mock.Mock:
        patcher = mock.patch.object(tasks, "run_full_analysis")
        analysis = patcher.start()
        self.addCleanup(patcher.stop)
        return analysis

    def test_import_votes_reports_vote_changes(self) -> None:
        self.mock_import(VoteImportResult(votes_updated=1))
        self.assertTrue(tasks.import_votes())

    def test_import_votes_reports_no_changes(self) -> None:
        self.mock_import(VoteImportResult(created=0, texts_fetched=3))
        self.assertFalse(tasks.import_votes())

    def test_analysis_runs_when_votes_changed(self) -> None:
        analysis = self.mock_analysis()
        tasks.run_scheduled_pca_analysis(True)
        analysis.assert_called_once_with(n_components=3)

    def test_analysis_skipped_without_vote_changes(self) -> None:
        analysis = self.mock_analysis()
        tasks.run_scheduled_pca_analysis(False)
        analysis.assert_not_called()

    def test_analysis_runs_by_default(self) -> None:
        analysis = self.mock_analysis()
        tasks.run_scheduled_pca_analysis()
        analysis.assert_called_once()

    def test_chain_runs_analysis_after_import_with_changes(self) -> None:
        api_class = self.mock_import(VoteImportResult(votes_created=5))
        analysis = self.mock_analysis()
        tasks.import_and_analyze()
        api_class.return_value.import_votes.assert_called_once()
        analysis.assert_called_once()

    def test_chain_skips_analysis_without_changes(self) -> None:
        self.mock_import(VoteImportResult())
        analysis = self.mock_analysis()
        tasks.import_and_analyze()
        analysis.assert_not_called()

    def test_chain_does_not_analyze_when_import_fails(self) -> None:
        api_class = self.mock_import(VoteImportResult())
        api_class.return_value.import_votes.side_effect = RuntimeError("boom")
        analysis = self.mock_analysis()
        with self.assertRaises(RuntimeError):
            tasks.import_and_analyze()
        analysis.assert_not_called()
