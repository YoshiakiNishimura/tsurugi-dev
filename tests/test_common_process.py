from __future__ import annotations

import unittest
from pathlib import Path

from tsurugi_dev.common.process import command_text


class ProcessHelperTests(unittest.TestCase):
    def test_command_text_with_cwd(self) -> None:
        text = command_text(["echo", "hello world"], cwd=Path("/tmp/work"))
        self.assertIn("cd /tmp/work", text)
        self.assertIn("'hello world'", text)


if __name__ == "__main__":
    unittest.main()
