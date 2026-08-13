from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
