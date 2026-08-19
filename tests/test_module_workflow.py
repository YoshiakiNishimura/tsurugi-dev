from __future__ import annotations

import argparse
import subprocess
import tempfile
import unittest
from pathlib import Path

from tsurugi_dev.module_workflow import (
    component_development_state,
    dev_finish,
    dev_start,
)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


class ModuleWorkflowTests(unittest.TestCase):
    def test_start_and_finish_component_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin = root / "origin.git"
            subprocess.run(
                ["git", "init", "--bare", str(origin)],
                check=True,
                stdout=subprocess.DEVNULL,
            )

            seed = root / "seed"
            seed.mkdir()
            git(seed, "init", "-b", "master")
            git(seed, "config", "user.name", "Test User")
            git(seed, "config", "user.email", "test@example.com")
            (seed / "file.txt").write_text("initial\n", encoding="utf-8")
            git(seed, "add", ".")
            git(seed, "commit", "-m", "initial")
            git(seed, "remote", "add", "origin", str(origin))
            git(seed, "push", "-u", "origin", "master")

            parent = root / "parent"
            parent.mkdir()
            git(parent, "init", "-b", "master")
            git(parent, "config", "user.name", "Test User")
            git(parent, "config", "user.email", "test@example.com")
            git(
                parent,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                str(origin),
                "jogasaki",
            )
            git(parent, "commit", "-am", "add submodule")

            sub = parent / "jogasaki"
            args = argparse.Namespace(
                repo=parent,
                component="jogasaki",
                branch="feature/test",
                base="master",
                remote="origin",
                dry_run=False,
            )
            dev_start(args)
            self.assertEqual(git(sub, "branch", "--show-current"), "feature/test")

            safe, reason = component_development_state(parent, "jogasaki")
            self.assertFalse(safe, reason)

            finish_args = argparse.Namespace(
                repo=parent,
                component="jogasaki",
                base="master",
                remote="origin",
                force_delete=False,
                dry_run=False,
            )
            dev_finish(finish_args)
            self.assertEqual(git(sub, "branch", "--show-current"), "master")

            safe, reason = component_development_state(parent, "jogasaki")
            self.assertTrue(safe, reason)


if __name__ == "__main__":
    unittest.main()
