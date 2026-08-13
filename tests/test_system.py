from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tsurugi_dev.common.system import GIB, choose_parallel, linux_mem_available_bytes


class ParallelTests(unittest.TestCase):
    def test_cpu_is_limit_when_memory_is_plentiful(self) -> None:
        decision = choose_parallel(cpu_count=16, memory_available_bytes=128 * GIB)
        self.assertEqual(decision.jobs, 16)

    def test_memory_can_limit_parallelism(self) -> None:
        # 16 GiB available, reserve 2 GiB, 2 GiB/job => 7 jobs.
        decision = choose_parallel(cpu_count=64, memory_available_bytes=16 * GIB)
        self.assertEqual(decision.jobs, 7)
        self.assertEqual(decision.memory_limit, 7)

    def test_at_least_one_job(self) -> None:
        decision = choose_parallel(cpu_count=8, memory_available_bytes=1 * GIB)
        self.assertEqual(decision.jobs, 1)

    def test_memavailable_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meminfo"
            path.write_text(
                "MemTotal: 100 kB\nMemAvailable: 4096 kB\n", encoding="utf-8"
            )
            self.assertEqual(linux_mem_available_bytes(path), 4096 * 1024)


if __name__ == "__main__":
    unittest.main()
