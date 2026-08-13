from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GIB = 1024**3
DEFAULT_MEMORY_PER_JOB_GIB = 2.0
DEFAULT_MEMORY_RESERVE_GIB = 2.0


@dataclass(frozen=True)
class ParallelDecision:
    jobs: int
    cpu_limit: int
    memory_limit: int | None
    memory_available_bytes: int | None
    memory_per_job_gib: float
    memory_reserve_gib: float

    @property
    def reason(self) -> str:
        if self.memory_limit is None:
            return f"cpu={self.cpu_limit}, memory=unknown"
        available = self.memory_available_bytes or 0
        return (
            f"cpu={self.cpu_limit}, memory={available / GIB:.1f} GiB, "
            f"memory-limit={self.memory_limit}"
        )


def available_cpu_count() -> int:
    """Return CPUs available to this process, respecting affinity when possible."""
    try:
        count = len(os.sched_getaffinity(0))
        if count > 0:
            return count
    except (AttributeError, OSError):
        pass
    return max(1, os.cpu_count() or 1)


def linux_mem_available_bytes(path: Path = Path("/proc/meminfo")) -> int | None:
    """Read Linux MemAvailable, or return None if unavailable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    for line in text.splitlines():
        if not line.startswith("MemAvailable:"):
            continue
        parts = line.split()
        if len(parts) < 2:
            return None
        try:
            kib = int(parts[1])
        except ValueError:
            return None
        return kib * 1024
    return None


def choose_parallel(
    *,
    cpu_count: int,
    memory_available_bytes: int | None,
    memory_per_job_gib: float = DEFAULT_MEMORY_PER_JOB_GIB,
    memory_reserve_gib: float = DEFAULT_MEMORY_RESERVE_GIB,
) -> ParallelDecision:
    """Choose conservative parallelism from CPU availability and free memory."""
    if cpu_count < 1:
        raise ValueError("cpu_count must be >= 1")
    if memory_per_job_gib <= 0:
        raise ValueError("memory_per_job_gib must be > 0")
    if memory_reserve_gib < 0:
        raise ValueError("memory_reserve_gib must be >= 0")

    memory_limit: int | None = None
    if memory_available_bytes is not None:
        reserve = int(memory_reserve_gib * GIB)
        per_job = int(memory_per_job_gib * GIB)
        usable = max(0, memory_available_bytes - reserve)
        memory_limit = max(1, usable // per_job)

    jobs = cpu_count if memory_limit is None else min(cpu_count, memory_limit)
    jobs = max(1, jobs)
    return ParallelDecision(
        jobs=jobs,
        cpu_limit=cpu_count,
        memory_limit=memory_limit,
        memory_available_bytes=memory_available_bytes,
        memory_per_job_gib=memory_per_job_gib,
        memory_reserve_gib=memory_reserve_gib,
    )


def auto_parallel(
    *,
    memory_per_job_gib: float = DEFAULT_MEMORY_PER_JOB_GIB,
    memory_reserve_gib: float = DEFAULT_MEMORY_RESERVE_GIB,
) -> ParallelDecision:
    """Inspect the current machine/process and select build parallelism."""
    return choose_parallel(
        cpu_count=available_cpu_count(),
        memory_available_bytes=linux_mem_available_bytes(),
        memory_per_job_gib=memory_per_job_gib,
        memory_reserve_gib=memory_reserve_gib,
    )
