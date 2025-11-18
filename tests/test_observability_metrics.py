from src.observability.metrics import (
    increment_counter,
    set_gauge,
    observe_latency,
    get_metrics_snapshot,
    reset_metrics,
)


def test_metrics_snapshot_accumulates_counts():
    reset_metrics()
    increment_counter("test_counter")
    increment_counter("test_counter", amount=2, labels={"route": "/example"})
    set_gauge("test_gauge", 5)
    observe_latency("test_latency", 100, labels={"route": "/example"})
    observe_latency("test_latency", 50, labels={"route": "/example"})

    snapshot = get_metrics_snapshot()
    counters = snapshot["counters"]["test_counter"]
    assert len(counters) == 2

    gauges = snapshot["gauges"]["test_gauge"]
    assert gauges[0]["value"] == 5

    hist = snapshot["histograms"]["test_latency"][0]["stats"]
    assert hist["count"] == 2
    assert hist["max"] == 100

