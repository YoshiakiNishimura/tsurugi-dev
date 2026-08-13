from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tsurugi_dev.common.git import (
    clone_repository_if_missing,
    update_repository,
    update_submodules,
)


class GitHelperTests(unittest.TestCase):
    @patch("tsurugi_dev.common.git.run")
    def test_clone_repository_if_missing(self, run_mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "tsurugidb"
            cloned = clone_repository_if_missing(
                repo,
                "git@github.com:project-tsurugi/tsurugidb.git",
                dry_run=True,
            )
        self.assertTrue(cloned)
        self.assertEqual(
            run_mock.call_args.args[0],
            [
                "git",
                "clone",
                "git@github.com:project-tsurugi/tsurugidb.git",
                str(repo),
            ],
        )

    @patch("tsurugi_dev.common.git.run")
    def test_clone_skipped_for_existing_git_tree(self, run_mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "tsurugidb"
            (repo / ".git").mkdir(parents=True)
            cloned = clone_repository_if_missing(repo, "example", dry_run=False)
        self.assertFalse(cloned)
        run_mock.assert_not_called()

    def test_existing_non_git_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "tsurugidb"
            repo.mkdir()
            with self.assertRaises(RuntimeError):
                clone_repository_if_missing(repo, "example", dry_run=False)

    @patch("tsurugi_dev.common.git.run")
    def test_update_repository_runs_pull_and_submodules(self, run_mock) -> None:
        repo = Path("/tmp/repo")
        update_repository(repo, jobs=4, dry_run=True)
        self.assertEqual(run_mock.call_count, 3)
        self.assertEqual(
            run_mock.call_args_list[0].args[0],
            ["git", "pull", "--ff-only"],
        )
        self.assertEqual(
            run_mock.call_args_list[2].args[0],
            ["git", "submodule", "update", "--init", "--recursive", "--jobs", "4"],
        )

    def test_submodule_jobs_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            update_submodules(Path("/tmp/repo"), jobs=0, dry_run=True)


if __name__ == "__main__":
    unittest.main()
