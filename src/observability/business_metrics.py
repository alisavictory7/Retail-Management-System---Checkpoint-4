from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from src.config import Config
from src.models import Refund, RefundStatus, Sale, ReturnRequest, ReturnRequestStatus

START_YEAR = 2025
END_YEAR = 2050
try:
    _LOCAL_TZ = ZoneInfo(getattr(Config, "DEFAULT_TIMEZONE", "UTC"))
except ZoneInfoNotFoundError:
    _LOCAL_TZ = timezone.utc


@dataclass(frozen=True)
class QuarterWindow:
    key: str
    label: str
    year: int
    quarter: int
    start: datetime
    end: datetime


def generate_quarter_windows(now: Optional[datetime] = None) -> List[QuarterWindow]:
    """Generate every quarter between START_YEAR and END_YEAR inclusive."""
    tz = timezone.utc
    windows: List[QuarterWindow] = []
    for year in range(START_YEAR, END_YEAR + 1):
        for quarter in range(1, 5):
            start_month = (quarter - 1) * 3 + 1
            start = datetime(year, start_month, 1, tzinfo=tz)
            if year == END_YEAR and quarter == 4:
                end = datetime(END_YEAR + 1, 1, 1, tzinfo=tz)
            elif quarter == 4:
                end = datetime(year + 1, 1, 1, tzinfo=tz)
            else:
                end = datetime(year, start_month + 3, 1, tzinfo=tz)
            key = f"{year}-Q{quarter}"
            label = f"Q{quarter} {year}"
            windows.append(QuarterWindow(key=key, label=label, year=year, quarter=quarter, start=start, end=end))
    return windows


def select_quarter_window(
    windows: List[QuarterWindow],
    selected_key: Optional[str],
    now: Optional[datetime] = None,
) -> QuarterWindow:
    """Return the requested quarter or fall back to the quarter that contains 'now'."""
    if selected_key:
        for window in windows:
            if window.key == selected_key:
                return window

    now = now or datetime.now(timezone.utc)
    for window in windows:
        if window.start <= now < window.end:
            return window
    # If 'now' is outside the configured range, fall back to the last window
    return windows[-1]


def compute_orders_metrics(
    session: Session,
    window: QuarterWindow,
    now: Optional[datetime] = None,
) -> Dict[str, float]:
    rows = (
        session.query(Sale._sale_date)
        .filter(Sale._sale_date >= window.start)
        .filter(Sale._sale_date < window.end)
        .filter(Sale._status == "completed")
        .all()
    )
    timestamps = [_to_local_timezone(row[0]) for row in rows if row[0] is not None]
    return _build_series_metrics(timestamps, window, now)


def compute_refund_metrics(
    session: Session,
    window: QuarterWindow,
    now: Optional[datetime] = None,
) -> Dict[str, float]:
    """
    Compute refund metrics for the given time window.
    Uses processed_at for completed refunds (when they were actually processed),
    falls back to created_at for refunds without processed_at.
    """
    rows = (
        session.query(Refund.processed_at, Refund.created_at)
        .filter(Refund.status == RefundStatus.COMPLETED)
        .all()
    )
    # Use processed_at if available (when refund was completed), otherwise created_at
    timestamps = []
    for row in rows:
        refund_date = row[0] if row[0] is not None else row[1]
        if refund_date is not None:
            # Ensure refund_date is timezone-aware (UTC)
            if refund_date.tzinfo is None:
                refund_date = refund_date.replace(tzinfo=timezone.utc)
            else:
                refund_date = refund_date.astimezone(timezone.utc)
            
            # Check if refund is within the window (window times are in UTC)
            if window.start <= refund_date < window.end:
                # Convert to local timezone for series building
                local_date = _to_local_timezone(refund_date)
                timestamps.append(local_date)
    
    return _build_series_metrics(timestamps, window, now)


def _to_local_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_LOCAL_TZ)


def _build_series_metrics(
    timestamps: List[datetime],
    window: QuarterWindow,
    now: Optional[datetime] = None,
) -> Dict[str, float]:
    counts: Counter = Counter(ts.date() for ts in timestamps)

    day = window.start
    series: List[Dict[str, float]] = []
    while day < window.end:
        local_day = day.astimezone(_LOCAL_TZ)
        date_key = local_day.date()
        series.append({"date": date_key.isoformat(), "count": counts.get(date_key, 0)})
        day += timedelta(days=1)

    total = sum(point["count"] for point in series)
    series_max = max((point["count"] for point in series), default=0)
    mean_per_day = total / len(series) if series else 0.0

    return {
        "total": total,
        "series": series,
        "series_max": series_max,
        "mean_per_day": mean_per_day,
    }


def compute_rma_summary(
    session: Session,
    window: QuarterWindow,
) -> Dict[str, float]:
    """Compute RMA volume and cycle time within the window."""
    tz_now = datetime.now(timezone.utc)
    requests = (
        session.query(ReturnRequest)
        .filter(ReturnRequest.created_at >= window.start)
        .filter(ReturnRequest.created_at < window.end)
        .all()
    )
    total_returns = len(requests)
    cycle_durations: List[float] = []
    for req in requests:
        if req.status in {
            ReturnRequestStatus.APPROVED,
            ReturnRequestStatus.REFUNDED,
            ReturnRequestStatus.REJECTED,
        }:
            start = _to_local_timezone(req.created_at)
            end_source = req.updated_at or tz_now
            end = _to_local_timezone(end_source)
            cycle_durations.append((end - start).total_seconds())

    avg_cycle_hours = (sum(cycle_durations) / len(cycle_durations) / 3600) if cycle_durations else 0.0

    return {
        "count": total_returns,
        "avg_cycle_hours": avg_cycle_hours,
    }


__all__ = [
    "QuarterWindow",
    "generate_quarter_windows",
    "select_quarter_window",
    "compute_orders_metrics",
    "compute_refund_metrics",
    "compute_rma_summary",
]

