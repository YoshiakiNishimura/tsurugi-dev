from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tsurugi_dev.common.java import apply_java_runtime, java_major, select_java_runtime


class JavaTests(unittest.TestCase):
    def _make_java(self, home: Path, version: int) -> Path:
        java = home / "bin" / "java"
        java.parent.mkdir(parents=True)
        java.write_text(
            f"#!/bin/sh\necho 'openjdk version \"{version}.0.1\"' >&2\n",
            encoding="utf-8",
        )
        java.chmod(0o755)
        return java

    def test_java_major(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            java = self._make_java(Path(tmp) / "jdk17", 17)
            self.assertEqual(java_major(java), 17)

    def test_select_prefers_java17_from_jvm_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "jvm"
            self._make_java(root / "jdk11", 11)
            self._make_java(root / "jdk17", 17)
            self._make_java(root / "jdk21", 21)
            runtime = select_java_runtime(
                env={"PATH": ""},
                jvm_root=root,
                min_major=17,
                preferred_major=17,
            )
            self.assertIsNotNone(runtime)
            assert runtime is not None
            self.assertEqual(runtime.major, 17)
            self.assertEqual(runtime.home, (root / "jdk17").resolve())

    def test_apply_java_runtime_does_not_mutate_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "jdk17"
            self._make_java(home, 17)
            runtime = select_java_runtime(explicit_home=home, env={"PATH": "/usr/bin"})
            assert runtime is not None
            original = {"PATH": "/usr/bin", "JAVA_HOME": "/old"}
            updated = apply_java_runtime(original, runtime)
            self.assertEqual(original["JAVA_HOME"], "/old")
            self.assertEqual(updated["JAVA_HOME"], str(home.resolve()))
            self.assertTrue(updated["PATH"].startswith(str(home.resolve() / "bin")))


if __name__ == "__main__":
    unittest.main()
