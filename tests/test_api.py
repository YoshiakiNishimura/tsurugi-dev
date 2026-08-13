from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tsurugi_dev.api import BuildRequest, full_build
from tsurugi_dev.upstream import InstallLayout


class ApiTests(unittest.TestCase):
    def test_build_request_enables_compatibility_by_default(self) -> None:
        request = BuildRequest(repo=Path("/tmp/repo"), home=Path("/tmp/home"))
        self.assertTrue(request.build_all_compat)
        self.assertEqual(request.parallel, "auto")

    @patch("tsurugi_dev.api.resolve_layout")
    @patch("tsurugi_dev.api.execute_build")
    def test_full_build_is_callable_without_argparse(
        self, execute_build, resolve_layout
    ) -> None:
        execute_build.return_value = 0
        resolve_layout.return_value = InstallLayout(
            home=Path("/tmp/home"),
            prefix=Path("/tmp"),
            name="dev-relwithdebinfo",
        )
        result = full_build(
            BuildRequest(repo=Path("/tmp/repo"), home=Path("/tmp/home"))
        )
        self.assertEqual(result.home, Path("/tmp/home"))
        args = execute_build.call_args.args[0]
        self.assertTrue(args.legacy_build_all_compat)


if __name__ == "__main__":
    unittest.main()
