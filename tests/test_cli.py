from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tsurugi_dev.cli import make_parser


class CliTests(unittest.TestCase):
    def test_build_parallel_defaults_to_auto(self) -> None:
        args = make_parser().parse_args(["build"])
        self.assertEqual(args.parallel, "auto")

    def test_build_parallel_integer(self) -> None:
        args = make_parser().parse_args(["build", "--parallel", "8"])
        self.assertEqual(args.parallel, 8)

    def test_diff_build_alias(self) -> None:
        args = make_parser().parse_args(["diff-build"])
        self.assertEqual(args.parallel, "auto")

    def test_repo_defaults_to_workspace_tsurugidb(self) -> None:
        with patch.dict(
            os.environ,
            {"TSURUGI_DEV_WORKSPACE": "/tmp/workspace"},
            clear=False,
        ):
            args = make_parser().parse_args(["update"])
        self.assertEqual(args.repo, Path("/tmp/workspace/tsurugidb"))


if __name__ == "__main__":
    unittest.main()
