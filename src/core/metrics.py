"""In-process operational metrics — counts + latency, no new dependencies.

Thread-safe counters for query attempts plus a small latency aggregate, exposed
read-only via ``GET /metrics``. **In-memory only** — resets on restart
(Phase-6 decision D-F). Counts and latency only; never query data, SQL, or
secrets. A Prometheus/scrape backend is a Phase-7 concern (D-A).
"""

from __future__ import annotations

import threading
from typing import Dict

_lock = threading.Lock()

_counters: Dict[str, int] = {
    "queries_executed": 0,
    "queries_rejected": 0,  # blocked by the SELECT-only safety layer
    "queries_errored": 0,   # reached the driver and raised
}

_latency = {"sum_seconds": 0.0, "count": 0, "max_seconds": 0.0}


def increment(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def observe_latency(seconds: float) -> None:
    with _lock:
        _latency["sum_seconds"] += seconds
        _latency["count"] += 1
        if seconds > _latency["max_seconds"]:
            _latency["max_seconds"] = seconds


def snapshot() -> Dict[str, object]:
    """A read-only view of current counters + latency (counts only, no secrets)."""
    with _lock:
        count = _latency["count"]
        avg = (_latency["sum_seconds"] / count) if count else 0.0
        return {
            "counters": dict(_counters),
            "latency_seconds": {
                "count": count,
                "avg": round(avg, 4),
                "max": round(_latency["max_seconds"], 4),
            },
        }


def reset() -> None:
    """Test-only: clear all counters and latency back to zero."""
    with _lock:
        for key in _counters:
            _counters[key] = 0
        _latency["sum_seconds"] = 0.0
        _latency["count"] = 0
        _latency["max_seconds"] = 0.0
