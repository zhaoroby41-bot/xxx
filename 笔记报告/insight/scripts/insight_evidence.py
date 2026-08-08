from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median
from typing import Any


REQUIRED_MODULES = (
    "growth_diagnosis",
    "matrix_health",
    "content_patterns",
    "user_signals",
    "regional_strategy",
    "action_plan",
    "business_opportunities",
)


def evidence(
    evidence_id: str,
    module: str,
    metric: str,
    value: Any,
    *,
    comparison: Any = None,
    scope: dict | None = None,
    sample_size: int | None = None,
    confidence: str = "supported",
) -> dict:
    return {
        "evidence_id": evidence_id,
        "module": module,
        "metric": metric,
        "value": value,
        "comparison": comparison,
        "scope": scope or {},
        "sample_size": sample_size,
        "confidence": confidence,
    }


def build_evidence_packet(role: str, payload: dict, history_context: dict, period: dict) -> dict:
    """Build deterministic analysis evidence without altering the source payload."""
    if role not in {"dealer", "apple"}:
        raise ValueError("role must be 'dealer' or 'apple'")
    if not isinstance(payload, dict) or not isinstance(history_context, dict) or not isinstance(period, dict):
        raise TypeError("payload, history_context, and period must be dictionaries")

    builders = (
        _growth_evidence,
        _matrix_health_evidence,
        _content_pattern_evidence,
        _user_signal_evidence,
        _regional_strategy_evidence,
        _action_evidence,
        _business_opportunity_evidence,
    )
    rows: list[dict] = []
    for builder in builders:
        rows.extend(builder(role, payload, history_context, period))
    rows.sort(key=lambda row: (REQUIRED_MODULES.index(row["module"]), row["evidence_id"]))
    module_status = {
        module: "ready" if any(
            row["module"] == module and row["scope"].get("availability") != "insufficient_data"
            for row in rows
        ) else "insufficient_data"
        for module in REQUIRED_MODULES
    }
    packet = {
        "schema_version": "1.0",
        "role": role,
        "period": _clean_number(dict(period)),
        "data_scope": _data_scope(role, payload, history_context),
        "module_status": module_status,
        "evidence": rows,
    }
    return _clean_number(packet)


def _growth_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    module = "growth_diagnosis"
    root = _root(role, payload)
    month = _month(payload, period)
    rows: list[dict] = []
    current = _growth_current(role, root)
    for metric, value in sorted(current.items()):
        if value is not None:
            rows.append(_row(role, root, month, module, "current_" + metric, value, scope={"cohort": "core_kpi" if metric in {"reads", "interactions", "fans"} else "all_scoped_accounts"}))

    comparisons = history.get("comparisons", {})
    aliases = {"previous_month": "previous", "year_ago": "year_ago", "rolling_baseline": "baseline"}
    for source, suffix in aliases.items():
        for metric in ("reads", "interactions", "new_fans"):
            change = _mapping(comparisons.get(source)).get(metric, {}).get("ratio_change")
            if _finite(change):
                output_metric = ("fans" if metric == "new_fans" else metric) + "_change_vs_" + suffix
                rows.append(_row(role, root, month, module, output_metric, change, comparison={"baseline": source}, scope={"history_source": source, "cohort": "all_scoped_accounts"}))

    for metric in ("reads", "interactions", "fans"):
        values = _mapping(_mapping(root).get("kpi") if role == "dealer" else _mapping(root).get("network_kpis")).get(metric, {})
        gap = values.get("pacing_gap")
        if _finite(gap):
            rows.append(_row(role, root, month, module, "q4_" + metric + "_pacing_gap", gap, comparison={"elapsed_ratio": values.get("elapsed_ratio", _mapping(root).get("elapsed_ratio"))}, scope={"cohort": "core_kpi", "fiscal_quarter": period.get("fiscal_quarter")}))

    prior = _mapping(comparisons.get("previous_month"))
    changes = [_number(prior.get(metric, {}).get("ratio_change")) for metric in ("reads", "interactions", "new_fans")]
    if all(value is not None for value in changes):
        rows.append(_row(role, root, month, module, "reads_interaction_fans_divergence", max(changes) - min(changes), scope={"history_source": "previous_month", "cohort": "all_scoped_accounts"}))
    return _or_placeholder(role, root, month, module, rows)


def _matrix_health_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history, period
    module = "matrix_health"
    root = _root(role, payload)
    month = _month(payload, {})
    rows: list[dict] = []
    content = _content(role, root)
    categories = _categories(role, root)
    note_count = _number(content.get("notes"))
    reads = _number(content.get("reads"))
    if note_count is not None:
        rows.append(_row(role, root, month, module, "top_20_read_share", 1.0 if note_count <= 20 else _top_category_read_share(categories, reads), scope={"aggregation": "available_content_snapshot", "cohort": "all_scoped_accounts"}))
        rows.append(_row(role, root, month, module, "long_tail_note_share", _long_tail_share(categories, note_count), scope={"cohort": "all_scoped_accounts"}))
    shares = [
        _number(item.get("note_share"))
        if _number(item.get("note_share")) is not None
        else ((_number(item.get("notes")) or 0) / note_count if note_count else None)
        for item in categories
    ]
    shares = [value for value in shares if value is not None]
    if shares:
        rows.append(_row(role, root, month, module, "content_homogeneity", sum(value * value for value in shares), scope={"method": "category_note_share_hhi", "cohort": "all_scoped_accounts"}, sample_size=len(shares)))
    if role == "dealer":
        rows.extend(_dealer_matrix_rows(root, month))
    else:
        rows.extend(_apple_matrix_rows(root, month))
    return _or_placeholder(role, root, month, module, rows)


def _content_pattern_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "content_patterns"
    root = _root(role, payload)
    month = _month(payload, period)
    content = _content(role, root)
    categories = _categories(role, root)
    notes = _note_rows(root)
    rows: list[dict] = []
    total_notes = _number(content.get("notes"))
    reads = _number(content.get("reads"))
    if total_notes is not None:
        threshold = _number(content.get("reads_per_note"))
        rows.append(_row(role, root, month, module, "top_20_note_count", min(20, total_notes), scope={"pattern_type": "top_20", "cohort": "all_scoped_accounts"}, sample_size=int(total_notes)))
        rows.append(_row(role, root, month, module, "viral_threshold_reads", (threshold or 0) * 2, scope={"pattern_type": "viral", "threshold_basis": "two_times_reads_per_note"}))
        rows.append(_row(role, root, month, module, "viral_rate", _viral_rate(notes, threshold, categories), scope={"pattern_type": "viral", "evidence_basis": "note_rows" if notes else "category_aggregate_proxy"}, sample_size=len(notes) if notes else int(total_notes)))
        rows.append(_row(role, root, month, module, "long_tail_note_count", _long_tail_count(categories, total_notes), scope={"pattern_type": "long_tail", "cohort": "all_scoped_accounts"}, sample_size=int(total_notes)))
        rows.append(_row(role, root, month, module, "hotspot_recency_days", _hotspot_recency(notes, month), scope={"pattern_type": "hotspot", "evidence_basis": "publication_date" if notes else "source_month_snapshot"}, sample_size=len(notes) if notes else int(total_notes)))
    if total_notes is not None:
        tokens = _title_tokens(notes)
        rows.append(_row(role, root, month, module, "title_token_count", len(tokens), scope={"pattern_type": "title_tokens", "evidence_basis": "note_titles" if notes else "not_available_in_payload"}, sample_size=len(notes), confidence="supported" if notes else "validate"))
    for category in categories:
        category_name = str(category.get("category", "unclassified"))
        value = _number(category.get("reads_per_note"))
        if value is not None:
            rows.append(_row(role, root, month, module, "category_reads_per_note", value, comparison={"interaction_rate": category.get("interaction_rate")}, scope={"category": category_name, "region": category.get("region", ""), "pattern_type": "category_performance", "cohort": category.get("cohort", "all_scoped_accounts")}, sample_size=_int(category.get("notes"))))
    for format_name, value in (("image", content.get("image_share")), ("video", content.get("video_share"))):
        if _finite(value):
            rows.append(_row(role, root, month, module, "format_note_share", value, scope={"format": format_name, "pattern_type": "format_performance"}, sample_size=_int(total_notes)))
    return _or_placeholder(role, root, month, module, rows)


def _user_signal_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "user_signals"
    root = _root(role, payload)
    month = _month(payload, period)
    accounts = _account_rows(role, root)
    content = _content(role, root)
    values = {metric: sum(_number(_mapping(account.get("metrics")).get(metric)) or 0 for account in accounts) for metric in ("reads", "likes", "collects", "comments", "shares", "new_fans")}
    if not accounts:
        values["reads"] = _number(content.get("reads")) or 0
        values["new_fans"] = _number(content.get("new_fans")) or 0
    rows: list[dict] = []
    if values["reads"] or accounts:
        for metric in ("likes", "collects", "comments", "shares"):
            rows.append(_row(role, root, month, module, metric + "_per_read", values[metric] / values["reads"] if values["reads"] else None, scope={"signal": metric, "cohort": "all_scoped_accounts"}, sample_size=len(accounts) or _int(content.get("notes"))))
        rows.append(_row(role, root, month, module, "fans_per_read", values["new_fans"] / values["reads"] if values["reads"] else None, scope={"signal": "fan_conversion", "cohort": "all_scoped_accounts"}, sample_size=len(accounts) or _int(content.get("notes"))))
        save_cutoff = median([_number(_mapping(account.get("metrics")).get("collects")) or 0 for account in accounts]) if accounts else 0
        comment_cutoff = median([_number(_mapping(account.get("metrics")).get("comments")) or 0 for account in accounts]) if accounts else 0
        rows.append(_row(role, root, month, module, "high_save_candidate_count", sum((_number(_mapping(account.get("metrics")).get("collects")) or 0) > save_cutoff for account in accounts), scope={"signal": "high_save", "candidate_unit": "account"}, sample_size=len(accounts)))
        rows.append(_row(role, root, month, module, "high_comment_candidate_count", sum((_number(_mapping(account.get("metrics")).get("comments")) or 0) > comment_cutoff for account in accounts), scope={"signal": "high_comment", "candidate_unit": "account"}, sample_size=len(accounts)))
        anomaly_count = sum((_number(_mapping(account.get("metrics")).get("reads")) or 0) == 0 and sum((_number(_mapping(account.get("metrics")).get(metric)) or 0) for metric in ("likes", "collects", "comments")) > 0 for account in accounts)
        rows.append(_row(role, root, month, module, "anomaly_candidate_count", anomaly_count, scope={"signal": "interactions_without_reads", "candidate_unit": "account"}, sample_size=len(accounts)))
    return _or_placeholder(role, root, month, module, rows)


def _regional_strategy_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "regional_strategy"
    root = _root(role, payload)
    month = _month(payload, period)
    rows: list[dict] = []
    for city in _city_segments(role, root):
        sample_size = _int(city.get("account_count"))
        note_count = _int(_mapping(city.get("content")).get("notes"))
        if sample_size is None:
            sample_size = _city_account_count(role, root, city.get("city"))
        if note_count is None:
            note_count = _int(_mapping(city.get("content")).get("notes"))
        sparse = (sample_size or 0) < 2 or (note_count or 0) < 3
        confidence = "validate" if sparse else "supported"
        efficiency = _number(city.get("reads_per_note"))
        if efficiency is None:
            efficiency = _number(_mapping(city.get("content")).get("reads_per_note"))
        if efficiency is None:
            efficiency = _number(city.get("reads"))
        rows.append(_row(role, root, month, module, "city_content_efficiency", efficiency, comparison={"notes": note_count}, scope={"city": city.get("city", "unassigned"), "region": city.get("region", "unassigned"), "cohort": city.get("cohort", "all_scoped_accounts"), "recommendation_mode": "test_only" if sparse else "supported"}, sample_size=sample_size, confidence=confidence))
        for category in _mapping(city.get("content")).get("categories", []):
            rows.append(_row(role, root, month, module, "city_category_efficiency", category.get("reads_per_note"), scope={"city": city.get("city", "unassigned"), "region": city.get("region", "unassigned"), "category": category.get("category", "unclassified"), "recommendation_mode": "test_only" if sparse else "supported"}, sample_size=sample_size, confidence=confidence))
    return _or_placeholder(role, root, month, module, rows)


def _action_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "action_plan"
    root = _root(role, payload)
    month = _month(payload, period)
    candidates = _actions(role, root)
    if not candidates:
        return _or_placeholder(role, root, month, module, [])
    rows: list[dict] = []
    for days in (30, 60, 90):
        matching = candidates if days == 30 else [item for item in candidates if item.get("priority") != "high"]
        rows.append(_row(role, root, month, module, "action_candidate_count", len(matching), comparison={"measurable_outcome": "pacing_gap_or_reads_per_note"}, scope={"horizon_days": days, "rule_ids": sorted(str(item.get("rule_id", item.get("id", ""))) for item in matching)}, sample_size=len(matching), confidence="supported" if matching else "validate"))
    return _or_placeholder(role, root, month, module, rows)


def _business_opportunity_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "business_opportunities"
    root = _root(role, payload)
    month = _month(payload, period)
    categories = _categories(role, root)
    content = _content(role, root)
    total_notes = _number(content.get("notes")) or 0
    total_reads = _number(content.get("reads")) or 0
    if not categories and not total_notes and not total_reads:
        return _or_placeholder(role, root, month, module, [])
    rows: list[dict] = []
    for scenario, terms in (
        ("trade_in", ("trade", "置换", "二手")),
        ("local_service", ("service", "服务", "本地")),
        ("installment_value", ("installment", "分期", "价值", "性价比")),
        ("women", ("women", "女性", "女生")),
        ("student", ("student", "学生")),
    ):
        matches = [item for item in categories if any(term in str(item.get("category", "")).lower() for term in terms)]
        demand = sum(_number(item.get("reads")) or 0 for item in matches) / total_reads if total_reads else 0
        supply = sum(_number(item.get("notes")) or 0 for item in matches) / total_notes if total_notes else 0
        concentration = sum((_number(item.get("note_share")) or 0) ** 2 for item in matches)
        rows.append(_row(role, root, month, module, "scenario_demand_share", demand, comparison={"supply_share": supply, "supply_gap": demand - supply, "competition_concentration": concentration}, scope={"scenario": scenario, "revalidation_required": True, "cohort": "all_scoped_accounts"}, sample_size=_int(sum(_number(item.get("notes")) or 0 for item in matches)), confidence="validate"))
    return _or_placeholder(role, root, month, module, rows)


def _dealer_matrix_rows(root: dict, month: str) -> list[dict]:
    rows: list[dict] = []
    accounts = _account_rows("dealer", root)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for account in accounts:
        grouped[str(account.get("cohort", "expanded_store"))].append(account)
    for cohort, members in sorted(grouped.items()):
        reads = [_number(_mapping(item.get("metrics")).get("reads")) or 0 for item in members]
        supply = [_number(_mapping(item.get("metrics")).get("notes")) or 1 for item in members]
        read_median, supply_median = median(reads), median(supply)
        for account, account_reads, account_supply in zip(members, reads, supply):
            quadrant = ("high_supply" if account_supply >= supply_median else "low_supply") + "_" + ("high_efficiency" if account_reads >= read_median else "low_efficiency")
            tier = "S" if account_reads >= read_median * 1.5 else "A" if account_reads >= read_median else "B" if account_reads >= read_median * 0.5 else "C"
            account_id = str(account.get("author_id", "unidentified"))
            rows.append(_row("dealer", root, month, "matrix_health", "account_quadrant", 1, scope={"cohort": cohort, "account_id": account_id, "quadrant": quadrant}, sample_size=len(members)))
            rows.append(_row("dealer", root, month, "matrix_health", "tier_candidate", 1, scope={"cohort": cohort, "account_id": account_id, "tier": tier}, sample_size=len(members)))
        rows.append(_row("dealer", root, month, "matrix_health", "posting_frequency", sum(supply) / len(supply), scope={"cohort": cohort, "unit": "notes_per_account"}, sample_size=len(members)))
    return rows


def _apple_matrix_rows(root: dict, month: str) -> list[dict]:
    rows: list[dict] = []
    quadrants = _mapping(root).get("dealer_quadrants", [])
    counts = Counter(str(item.get("quadrant", "unclassified")) for item in quadrants)
    for quadrant, count in sorted(counts.items()):
        rows.append(_row("apple", root, month, "matrix_health", "quadrant_distribution", count, scope={"quadrant": quadrant, "cohort": "network"}, sample_size=len(quadrants)))
    for tier, count in sorted(_mapping(root).get("status_counts", {}).items()):
        rows.append(_row("apple", root, month, "matrix_health", "tier_candidate_count", count, scope={"tier": tier, "cohort": "core_kpi"}, sample_size=sum(_mapping(root).get("status_counts", {}).values())))
    return rows


def _data_scope(role: str, payload: dict, history: dict) -> dict:
    root = _root(role, payload)
    accounts = _account_rows(role, root)
    cohorts = Counter(str(item.get("cohort", "expanded_store")) for item in accounts)
    apple_counts = _mapping(root.get("account_counts")) if role == "apple" else {}
    return {
        "role_scope": role,
        "source_month": _month(payload, {}),
        "history_months": _mapping(history.get("coverage")).get("months", 0),
        "history_first_month": _mapping(history.get("coverage")).get("first_month"),
        "account_cohorts": {
            "core_kpi": cohorts["core_kpi"] if role == "dealer" else _int(apple_counts.get("core_kpi")) or 0,
            "expanded_store": cohorts["expanded_store"] if role == "dealer" else _int(apple_counts.get("expanded_store")) or 0,
        },
        "quality_status": _mapping(payload.get("quality")).get("quality_status", "unknown"),
    }


def _root(role: str, payload: dict) -> dict:
    return _mapping(payload.get(role)) if isinstance(payload.get(role), dict) else _mapping(payload)


def _month(payload: dict, period: dict) -> str:
    return str(period.get("calendar_month") or payload.get("source_month") or "unknown-month")


def _growth_current(role: str, root: dict) -> dict[str, float | None]:
    if role == "dealer":
        content = _mapping(root.get("content"))
        kpi = _mapping(root.get("kpi"))
    else:
        content = _content(role, root)
        kpi = _mapping(root.get("network_kpis"))
    return {
        "reads": _number(kpi.get("reads", {}).get("actual")) if _mapping(kpi.get("reads")) else _number(content.get("reads")),
        "interactions": _number(kpi.get("interactions", {}).get("actual")) if _mapping(kpi.get("interactions")) else _number(content.get("interactions")),
        "fans": _number(kpi.get("fans", {}).get("actual")) if _mapping(kpi.get("fans")) else _number(content.get("new_fans")),
    }


def _content(role: str, root: dict) -> dict:
    if role == "dealer":
        return _mapping(root.get("content"))
    categories = _mapping(root).get("category_mix_performance", [])
    values = {"notes": 0.0, "reads": 0.0, "interactions": 0.0, "new_fans": 0.0}
    for category in categories:
        for metric in values:
            values[metric] += _number(category.get(metric)) or 0
    values["reads_per_note"] = values["reads"] / values["notes"] if values["notes"] else None
    values["interaction_rate"] = values["interactions"] / values["reads"] if values["reads"] else None
    return values


def _categories(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root.get("content")).get("categories", []) if isinstance(item, dict)]
    return [item for item in _mapping(root).get("category_mix_performance", []) if isinstance(item, dict)]


def _account_rows(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root).get("accounts", []) if isinstance(item, dict)]
    return []


def _note_rows(root: dict) -> list[dict]:
    candidates = root.get("notes") or _mapping(root.get("content")).get("note_rows") or []
    return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []


def _city_segments(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root.get("content")).get("by_city_cohort", []) if isinstance(item, dict)]
    return [item for item in _mapping(root).get("city_summaries", []) if isinstance(item, dict)]


def _city_account_count(role: str, root: dict, city: Any) -> int:
    return sum(item.get("city") == city for item in _account_rows(role, root)) if role == "dealer" else 0


def _actions(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root).get("recommendations", []) if isinstance(item, dict)]
    actions = []
    for bucket in _mapping(root).get("actions", {}).values():
        if isinstance(bucket, list):
            actions.extend(item for item in bucket if isinstance(item, dict))
    return actions


def _row(role: str, root: dict, month: str, module: str, metric: str, value: Any, *, comparison: Any = None, scope: dict | None = None, sample_size: int | None = None, confidence: str = "supported") -> dict:
    return evidence(_evidence_id(role, root, month, scope or {}, metric), module, metric, value, comparison=comparison, scope=scope, sample_size=sample_size, confidence=confidence)


def _or_placeholder(role: str, root: dict, month: str, module: str, rows: list[dict]) -> list[dict]:
    if rows:
        return rows
    return [_row(role, root, month, module, "insufficient_data", 0, scope={"availability": "insufficient_data"}, confidence="validate")]


def _evidence_id(role: str, root: dict, month: str, scope: dict, metric: str) -> str:
    if role == "dealer":
        subject = str(root.get("dealer_id", "unknown-dealer"))
        prefix = f"dealer:{subject}:{month}"
    else:
        prefix = f"apple:{month}"
    parts = [str(scope[key]) for key in ("cohort", "city", "region", "category", "account_id", "scenario", "horizon_days", "quadrant", "tier", "pattern_type", "format") if scope.get(key) not in (None, "")]
    return ":".join([prefix, *parts, metric])


def _top_category_read_share(categories: list[dict], total_reads: float | None) -> float | None:
    if not total_reads:
        return None
    return sum(sorted((_number(item.get("reads")) or 0 for item in categories), reverse=True)[:20]) / total_reads


def _long_tail_share(categories: list[dict], total_notes: float) -> float | None:
    if not total_notes:
        return None
    return _long_tail_count(categories, total_notes) / total_notes


def _long_tail_count(categories: list[dict], total_notes: float) -> float:
    if not categories:
        return 0
    median_reads = median([_number(item.get("reads_per_note")) or 0 for item in categories])
    return sum(_number(item.get("notes")) or 0 for item in categories if (_number(item.get("reads_per_note")) or 0) < median_reads)


def _viral_rate(notes: list[dict], threshold: float | None, categories: list[dict]) -> float:
    if notes:
        return sum((_number(item.get("reads")) or 0) >= (threshold or 0) * 2 for item in notes) / len(notes)
    if not categories:
        return 0.0
    return sum((_number(item.get("reads_per_note")) or 0) >= (threshold or 0) * 2 for item in categories) / len(categories)


def _hotspot_recency(notes: list[dict], month: str) -> int:
    if not notes:
        return 0
    dates = []
    for note in notes:
        value = str(note.get("publish_date", note.get("published_at", "")))[:10]
        try:
            dates.append(datetime.strptime(value, "%Y-%m-%d"))
        except ValueError:
            continue
    if not dates:
        return 0
    try:
        snapshot = datetime.strptime(month + "-01", "%Y-%m-%d")
    except ValueError:
        return 0
    return max(0, (snapshot - max(dates)).days)


def _title_tokens(notes: list[dict]) -> Counter:
    tokens: Counter = Counter()
    for note in notes:
        tokens.update(token.lower() for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", str(note.get("title", ""))))
    return tokens


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _finite(value: Any) -> bool:
    return _number(value) is not None


def _int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _clean_number(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _clean_number(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_number(item) for item in value]
    if isinstance(value, tuple):
        return [_clean_number(item) for item in value]
    return value
