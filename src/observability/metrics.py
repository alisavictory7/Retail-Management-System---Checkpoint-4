from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Tuple, Any, Optional

MetricKey = Tuple[str, Tuple[Tuple[str, str], ...]]


def _labels_tuple(labels: Optional[Dict[str, str]]) -> Tuple[Tuple[str, str], ...]:
    if not labels:
        return ()
    return tuple(sorted(labels.items()))


@dataclass
class Histogram:
    count: int = 0
    total: float = 0.0
    min_value: float = field(default=float("inf"))
    max_value: float = field(default=float("-inf"))

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

    def snapshot(self) -> Dict[str, Any]:
        avg = self.total / self.count if self.count else 0.0
        return {
            "count": self.count,
            "avg": avg,
            "min": None if self.count == 0 else self.min_value,
            "max": None if self.count == 0 else self.max_value,
        }


_counter_lock = threading.Lock()
_counters: Dict[MetricKey, float] = defaultdict(float)
_gauges: Dict[MetricKey, float] = {}
_histograms: Dict[MetricKey, Histogram] = {}
_events: list[Dict[str, Any]] = []
_max_events = 100


def increment_counter(name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    with _counter_lock:
        _counters[(name, _labels_tuple(labels))] += amount


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    with _counter_lock:
        _gauges[(name, _labels_tuple(labels))] = value


def observe_latency(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    with _counter_lock:
        key = (name, _labels_tuple(labels))
        histogram = _histograms.setdefault(key, Histogram())
        histogram.observe(value)


def record_event(name: str, payload: Dict[str, Any]) -> None:
    event = {"name": name, "timestamp": time.time(), "payload": payload}
    with _counter_lock:
        _events.append(event)
        if len(_events) > _max_events:
            _events.pop(0)


def get_metrics_snapshot() -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {"counters": {}, "gauges": {}, "histograms": {}, "events": list(_events)}
    with _counter_lock:
        for (name, labels), value in _counters.items():
            snapshot["counters"][name] = snapshot["counters"].get(name, [])
            snapshot["counters"][name].append({"labels": dict(labels), "value": value})

        for (name, labels), value in _gauges.items():
            snapshot["gauges"][name] = snapshot["gauges"].get(name, [])
            snapshot["gauges"][name].append({"labels": dict(labels), "value": value})

        for (name, labels), histogram in _histograms.items():
            snapshot["histograms"][name] = snapshot["histograms"].get(name, [])
            snapshot["histograms"][name].append(
                {"labels": dict(labels), "stats": histogram.snapshot()}
            )

    return snapshot


def reset_metrics() -> None:
    """Testing helper."""
    with _counter_lock:
        _counters.clear()
        _gauges.clear()
        _histograms.clear()
        _events.clear()

