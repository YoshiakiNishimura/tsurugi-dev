from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tsurugi_dev.config import (
    default_config,
    default_home,
    default_repo,
    default_workspace,
)


class ConfigTests(unittest.TestCase):
    def test_workspace_environment_wins(self) -> None:
        with patch.dict(
            os.environ,
            {"TSURUGI_DEV_WORKSPACE": "/tmp/tsurugi-workspace"},
            clear=False,
        ):
            self.assertEqual(default_workspace(), Path("/tmp/tsurugi-workspace"))
            self.assertEqual(
                default_repo(),
                Path("/tmp/tsurugi-workspace/tsurugidb"),
            )

    def test_tsurugi_home_environment_wins(self) -> None:
        with patch.dict(
            os.environ, {"TSURUGI_HOME": "/tmp/custom-tsurugi"}, clear=False
        ):
            self.assertEqual(default_home(), Path("/tmp/custom-tsurugi"))

    def test_tsurugi_home_falls_back_to_workspace(self) -> None:
        env = {"TSURUGI_DEV_WORKSPACE": "/tmp/workspace"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(default_home(), Path("/tmp/workspace/tsurugi"))

    def test_tsurugi_conf_environment_wins(self) -> None:
        with patch.dict(os.environ, {"TSURUGI_CONF": "/tmp/tsurugi.ini"}, clear=False):
            self.assertEqual(default_config(Path("/x")), Path("/tmp/tsurugi.ini"))


if __name__ == "__main__":
    unittest.main()
