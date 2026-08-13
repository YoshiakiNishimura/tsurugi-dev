from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tsurugi_dev.config import default_config, default_home


class ConfigTests(unittest.TestCase):
    def test_tsurugi_home_environment_wins(self) -> None:
        with patch.dict(
            os.environ, {"TSURUGI_HOME": "/tmp/custom-tsurugi"}, clear=False
        ):
            self.assertEqual(default_home(), Path("/tmp/custom-tsurugi"))

    def test_tsurugi_conf_environment_wins(self) -> None:
        with patch.dict(os.environ, {"TSURUGI_CONF": "/tmp/tsurugi.ini"}, clear=False):
            self.assertEqual(default_config(Path("/x")), Path("/tmp/tsurugi.ini"))


if __name__ == "__main__":
    unittest.main()
