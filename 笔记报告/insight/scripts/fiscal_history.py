from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
from statistics import median
from typing import Any


@dataclass(frozen=True)
class HistoricalSource:
    month: str
    path: Path


_MONTH_RE = re.compile(r"(?<!\d)(20\d{2})\s*[-年]\s*(\d{1,2})(?:月)?(?!\d)")
_TOTAL_DATA_RE = re.compile(r"总数据")


def _parse_month(month: str) -> datetime:
    return datetime.strptime(month, "%Y-%m")


def apple_period(month: str) -> dict[str, Any]:
    parsed = _parse_month(month)
    fiscal_year = parsed.year + 1 if parsed.month >= 10 else parsed.year
    fiscal_month = ((parsed.month - 10) % 12) + 1
    quarter = ((fiscal_month - 1) // 3) + 1
    return {
        "calendar_month": month,
        "fiscal_year": f"FY{str(fiscal_year)[-2:]}",
        "fiscal_quarter": f"Q{quarter}",
        "fiscal_month": fiscal_month - ((quarter - 1) * 3),
    }


def _month_from_filename(name: str) -> str | None:
    if not _TOTAL_DATA_RE.search(name):
        return None
    match = _MONTH_RE.search(name)
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}"


def discover_history_workbooks(data_root: Path, through_month: str) -> list[HistoricalSource]:
    _parse_month(through_month)
    found: dict[str, Path] = {}
    for path in sorted(data_root.rglob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        month = _month_from_filename(path.stem)
        if month is None or month >= through_month:
            continue
        if month in found:
            raise ValueError(f"duplicate historical source for {month}: {found[month]} and {path}")
        found[month] = path
    return [HistoricalSource(month, found[month]) for month in sorted(found)]


def safe_ratio_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline


def _median_metrics(rows: list[dict], metrics: tuple[str, ...]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for metric in metrics:
        values = [row[metric] for row in rows if row.get(metric) is not None]
        result[metric] = median(values) if values else None
    return result


def _comparison(current: dict, baseline: dict | None, metrics: tuple[str, ...]) -> dict[str, dict[str, float | None]]:
    return {
        metric: {
            "absolute_change": None if baseline is None else current.get(metric, None) - baseline.get(metric, None)
            if current.get(metric) is not None and baseline.get(metric) is not None else None,
            "ratio_change": safe_ratio_change(current.get(metric), None if baseline is None else baseline.get(metric)),
        }
        for metric in metrics
    }


def build_history_context(current: dict, history: list[dict]) -> dict:
    parsed_current = _parse_month(current["month"])
    ordered = sorted((row for row in history if row["month"] < current["month"]), key=lambda row: row["month"])
    if parsed_current.month == 1:
        previous_month = f"{parsed_current.year - 1:04d}-12"
    else:
        previous_month = f"{parsed_current.year:04d}-{parsed_current.month - 1:02d}"
    previous = next((row for row in ordered if row["month"] == previous_month), None)
    year_ago_month = f"{int(current['month'][:4]) - 1}{current['month'][4:]}"
    year_ago = next((row for row in ordered if row["month"] == year_ago_month), None)
    window = ordered[-12:]
    metrics = ("reads", "notes", "interactions", "new_fans", "viral_rate")
    baseline = _median_metrics(window, metrics)
    return {
        "previous_month": previous,
        "year_ago": year_ago,
        "rolling_baseline": baseline,
        "comparisons": {
            "previous_month": _comparison(current, previous, metrics),
            "year_ago": _comparison(current, year_ago, metrics),
            "rolling_baseline": _comparison(current, baseline, metrics),
        },
        "coverage": {"first_month": ordered[0]["month"] if ordered else None, "months": len(ordered)},
    }
