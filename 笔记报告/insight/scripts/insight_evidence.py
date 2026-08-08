from __future__ import annotations

import math
import re
from calendar import monthrange
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
PUBLISHABLE_QUALITY_STATUSES = {"ready", "ready_with_warnings"}


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

    root = _root(role, payload)
    quality_status = _quality_status(payload, root)
    if quality_status not in PUBLISHABLE_QUALITY_STATUSES:
        month = _month(payload, period)
        rows = [
            _unavailable_row(role, root, month, module, "quality_gate_unavailable", {"quality_status": quality_status})
            for module in REQUIRED_MODULES
        ]
        return _evidence_packet(role, payload, history_context, period, rows)

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
    return _evidence_packet(role, payload, history_context, period, rows)


def _evidence_packet(role: str, payload: dict, history_context: dict, period: dict, rows: list[dict]) -> dict:
    rows = _with_unique_evidence_ids(rows)
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

    kpi_container = _mapping(root.get("kpi") if role == "dealer" else root.get("network_kpis"))
    for metric in ("reads", "interactions", "fans"):
        values = _mapping(kpi_container.get(metric))
        gap = values.get("pacing_gap")
        if _finite(gap):
            elapsed_ratio = _number(kpi_container.get("elapsed_ratio"))
            quarter = _fiscal_quarter_key(period.get("fiscal_quarter"))
            rows.append(_row(role, root, month, module, quarter + "_" + metric + "_pacing_gap", gap, comparison={"elapsed_ratio": elapsed_ratio} if elapsed_ratio is not None else None, scope={"cohort": "core_kpi", "fiscal_quarter": period.get("fiscal_quarter")}))

    prior = _mapping(comparisons.get("previous_month"))
    changes = [_number(prior.get(metric, {}).get("ratio_change")) for metric in ("reads", "interactions", "new_fans")]
    if all(value is not None for value in changes):
        rows.append(_row(role, root, month, module, "reads_interaction_fans_divergence", max(changes) - min(changes), scope={"history_source": "previous_month", "cohort": "all_scoped_accounts"}))
    return _or_placeholder(role, root, month, module, rows)


def _matrix_health_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "matrix_health"
    root = _root(role, payload)
    month = _month(payload, period)
    rows: list[dict] = []
    content = _content(role, root)
    categories = _categories(role, root)
    note_count = _number(content.get("notes"))
    notes = _note_rows(root)
    explicit_top_20_share = _number(content.get("top_20_read_share"))
    if explicit_top_20_share is None:
        explicit_top_20_share = _number(root.get("top_20_read_share"))
    reads_coverage = _note_reads_coverage(notes) if notes else None
    if notes and _note_reads_are_complete(notes):
        top_20_share = _top_20_note_read_share(notes)
        top_20_basis = "note_rows"
    elif explicit_top_20_share is not None:
        top_20_share = explicit_top_20_share
        top_20_basis = "explicit_top20_aggregate"
    else:
        top_20_share = None
        top_20_basis = ""
    if top_20_share is not None:
        scope = {"evidence_basis": top_20_basis, "cohort": "all_scoped_accounts"}
        if notes and top_20_basis == "explicit_top20_aggregate":
            scope["reads_coverage"] = reads_coverage
        rows.append(_row(role, root, month, module, "top_20_read_share", top_20_share, scope=scope, sample_size=min(20, len(_ranked_notes_by_reads(notes))) if notes and top_20_basis == "note_rows" else None))
    else:
        unavailable_scope = {"evidence_basis": "note_rows_or_explicit_top20_aggregate", "cohort": "all_scoped_accounts"}
        if notes:
            unavailable_scope.update({"evidence_basis": "complete_note_reads_required", "reads_coverage": reads_coverage})
        rows.append(_unavailable_row(role, root, month, module, "top_20_read_share_unavailable", unavailable_scope))
    if note_count is not None and note_count > 0:
        long_tail_share = _long_tail_share(categories, note_count)
        if long_tail_share is not None:
            rows.append(_row(role, root, month, module, "long_tail_note_share", long_tail_share, scope={"cohort": "all_scoped_accounts"}))
    shares = [
        _number(item.get("note_share"))
        if _number(item.get("note_share")) is not None
        else ((_number(item.get("notes")) or 0) / note_count if note_count else None)
        for item in categories
    ]
    shares = [value for value in shares if value is not None]
    if shares:
        rows.append(_row(role, root, month, module, "content_homogeneity", sum(value * value for value in shares), scope={"method": "category_note_share_hhi", "cohort": "all_scoped_accounts"}, sample_size=len(shares)))
    rows.extend(_category_share_similarity_rows(role, root, month))
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
    rows: list[dict] = []
    note_rows = _note_rows(root)
    scopes = _content_scopes(role, root)
    for cohort, content, categories, evidence_basis in scopes:
        notes = _notes_for_cohort(note_rows, cohort, len(scopes))
        rows.extend(_content_pattern_scope_rows(role, root, month, module, cohort, content, categories, evidence_basis, notes))
    return _or_placeholder(role, root, month, module, rows)


def _content_pattern_scope_rows(role: str, root: dict, month: str, module: str, cohort: str, content: dict, categories: list[dict], aggregate_basis: str, notes: list[dict]) -> list[dict]:
    rows: list[dict] = []
    total_notes = _number(content.get("notes"))
    threshold = _number(content.get("reads_per_note"))
    aggregate_scope = {"cohort": cohort, "evidence_basis": aggregate_basis}
    if total_notes is not None and total_notes > 0:
        rows.append(_row(role, root, month, module, "aggregate_note_count", total_notes, scope={**aggregate_scope, "pattern_type": "aggregate_content"}, sample_size=int(total_notes)))
        if threshold is not None:
            rows.append(_row(role, root, month, module, "aggregate_reads_per_note", threshold, scope={**aggregate_scope, "pattern_type": "aggregate_content"}, sample_size=int(total_notes)))
        rows.append(_row(role, root, month, module, "long_tail_note_count", _long_tail_count(categories, total_notes), scope={**aggregate_scope, "pattern_type": "long_tail"}, sample_size=int(total_notes)))
    if notes:
        ranked_notes = _ranked_notes_by_reads(notes)
        reads_coverage = _note_reads_coverage(notes)
        reads_are_complete = _note_reads_are_complete(notes)
        note_scope = {"cohort": cohort, "evidence_basis": "note_rows", "reads_coverage": reads_coverage}
        rows.append(_row(role, root, month, module, "top_20_note_count", min(20, len(ranked_notes)), scope={**note_scope, "pattern_type": "top_20"}, sample_size=len(ranked_notes)))
        total_note_reads = sum(reads for _, reads in ranked_notes)
        for rank, (note, reads) in enumerate(ranked_notes[:20], start=1):
            note_id = _note_id(note)
            read_share = {"read_share": reads / total_note_reads} if reads_are_complete and total_note_reads else None
            rows.append(_row(role, root, month, module, "top_note_reads", reads, comparison=read_share, scope={**note_scope, "pattern_type": "top_20", "note_id": note_id, "note_rank": rank}, sample_size=len(ranked_notes)))
        if threshold is not None and reads_are_complete:
            rows.append(_row(role, root, month, module, "viral_threshold_reads", threshold * 2, scope={**note_scope, "pattern_type": "viral", "threshold_basis": "two_times_reads_per_note"}))
            rows.append(_row(role, root, month, module, "viral_rate", _viral_rate(notes, threshold, categories), scope={**note_scope, "pattern_type": "viral"}, sample_size=len(notes)))
        else:
            evidence_basis = "complete_note_reads_required" if not reads_are_complete else "reads_per_note"
            rows.append(_unavailable_row(role, root, month, module, "viral_rate_unavailable", {**note_scope, "pattern_type": "viral", "evidence_basis": evidence_basis}, sample_size=len(notes)))
        hotspot_recency = _hotspot_recency(notes, month)
        if hotspot_recency is None:
            rows.append(_unavailable_row(role, root, month, module, "hotspot_recency_unavailable", {**note_scope, "pattern_type": "hotspot", "evidence_basis": "publication_date"}, sample_size=len(notes)))
        else:
            rows.append(_row(role, root, month, module, "hotspot_recency_days", hotspot_recency, scope={**note_scope, "pattern_type": "hotspot", "evidence_basis": "publication_date"}, sample_size=len(notes)))
        title_tokens = _title_tokens(notes)
        if title_tokens:
            rows.append(_row(role, root, month, module, "title_token_count", len(title_tokens), scope={**note_scope, "pattern_type": "title_tokens", "evidence_basis": "note_titles", "top_token": _top_token(title_tokens)}, sample_size=len(notes)))
            for token, count in _top_tokens(title_tokens):
                rows.append(_row(role, root, month, module, "title_token_frequency", count, scope={**note_scope, "pattern_type": "title_tokens", "evidence_basis": "note_titles", "token": token}, sample_size=len(notes)))
        else:
            rows.append(_unavailable_row(role, root, month, module, "title_tokens_unavailable", {**note_scope, "pattern_type": "title_tokens", "evidence_basis": "note_titles"}, sample_size=len(notes)))
        _add_note_long_tail_evidence(role, root, month, module, ranked_notes, rows, cohort)
    else:
        if categories and threshold is not None:
            rows.append(_row(role, root, month, module, "viral_category_proxy_rate", _viral_rate([], threshold, categories), scope={**aggregate_scope, "pattern_type": "viral", "evidence_basis": "category_aggregate_proxy"}, sample_size=len(categories), confidence="validate"))
        else:
            rows.append(_unavailable_row(role, root, month, module, "viral_rate_unavailable", {**aggregate_scope, "pattern_type": "viral", "evidence_basis": "category_aggregate_proxy"}))
        rows.append(_unavailable_row(role, root, month, module, "top_20_notes_unavailable", {**aggregate_scope, "pattern_type": "top_20", "evidence_basis": "note_rows"}))
        rows.append(_unavailable_row(role, root, month, module, "hotspot_recency_unavailable", {**aggregate_scope, "pattern_type": "hotspot", "evidence_basis": "publication_date"}))
        rows.append(_unavailable_row(role, root, month, module, "title_tokens_unavailable", {**aggregate_scope, "pattern_type": "title_tokens", "evidence_basis": "note_titles"}))
    for category in categories:
        category_name = str(category.get("category", "unclassified"))
        value = _number(category.get("reads_per_note"))
        if value is not None:
            interaction_rate = _number(category.get("interaction_rate"))
            rows.append(_row(role, root, month, module, "category_reads_per_note", value, comparison={"interaction_rate": interaction_rate} if interaction_rate is not None else None, scope={**aggregate_scope, "category": category_name, "region": category.get("region", ""), "pattern_type": "category_performance"}, sample_size=_int(category.get("notes"))))
    for format_name, value in (("image", content.get("image_share")), ("video", content.get("video_share"))):
        if _finite(value):
            rows.append(_row(role, root, month, module, "format_note_share", value, scope={**aggregate_scope, "format": format_name, "pattern_type": "format_performance"}, sample_size=_int(total_notes)))
    return rows


def _user_signal_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "user_signals"
    root = _root(role, payload)
    month = _month(payload, period)
    accounts = _account_rows(role, root)
    notes = _note_rows(root)
    rows: list[dict] = []
    if accounts:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for account in accounts:
            grouped[str(account.get("cohort", "expanded_store"))].append(account)
        for cohort, members in sorted(grouped.items()):
            rows.extend(_account_user_signal_rows(role, root, month, module, cohort, members, not notes))
    if notes:
        note_cohorts = {str(note.get("cohort")) for note in notes if note.get("cohort") not in (None, "")}
        if len(note_cohorts) > 1:
            grouped_notes: dict[str, list[dict]] = defaultdict(list)
            for note in notes:
                cohort = str(note.get("cohort") or "all_scoped_accounts")
                grouped_notes[cohort].append(note)
            for cohort, members in sorted(grouped_notes.items()):
                _add_note_user_candidates(role, root, month, module, members, rows, cohort)
        else:
            _add_note_user_candidates(role, root, month, module, notes, rows, "all_scoped_accounts")
    elif not accounts:
        content = _content(role, root)
        reads, new_fans = _number(content.get("reads")), _number(content.get("new_fans"))
        if reads is not None and reads > 0:
            for metric in ("likes", "collects", "comments", "shares"):
                value = _number(content.get(metric))
                if value is not None:
                    rows.append(_row(role, root, month, module, metric + "_per_read", value / reads, scope={"signal": metric, "cohort": "all_scoped_accounts", "evidence_basis": "aggregate_content_summary"}, sample_size=_int(content.get("notes"))))
            if new_fans is not None:
                rows.append(_row(role, root, month, module, "fans_per_read", new_fans / reads, scope={"signal": "fan_conversion", "cohort": "all_scoped_accounts", "evidence_basis": "aggregate_content_summary"}, sample_size=_int(content.get("notes"))))
        rows.append(_unavailable_row(role, root, month, module, "high_save_candidates_unavailable", {"signal": "high_save", "candidate_unit": "unavailable"}))
        rows.append(_unavailable_row(role, root, month, module, "high_comment_candidates_unavailable", {"signal": "high_comment", "candidate_unit": "unavailable"}))
    return _or_placeholder(role, root, month, module, rows)


def _regional_strategy_evidence(role: str, payload: dict, history: dict, period: dict) -> list[dict]:
    del history
    module = "regional_strategy"
    root = _root(role, payload)
    month = _month(payload, period)
    rows: list[dict] = []
    cities = _city_segments(role, root) if role == "dealer" else _apple_city_segments(payload, root)
    for city in cities:
        sample_size = _int(city.get("account_count"))
        content = _mapping(city.get("content"))
        note_count = _int(content.get("notes"))
        if role == "dealer":
            sample_size = _city_account_count(role, root, city.get("city"), city.get("cohort"))
        elif sample_size is None:
            sample_size = _city_account_count(role, root, city.get("city"))
        sparse = (sample_size or 0) < 2 or (note_count or 0) < 3
        confidence = "validate" if sparse else "supported"
        efficiency = _number(city.get("reads_per_note"))
        if efficiency is None:
            efficiency = _number(content.get("reads_per_note"))
        if efficiency is None:
            reads = _number(content.get("reads"))
            efficiency = reads / note_count if reads is not None and note_count and note_count > 0 else None
        scope = {
            "city": city.get("city", "unassigned"),
            "region": city.get("region", "unassigned"),
            "cohort": city.get("cohort", "all_scoped_accounts"),
            "recommendation_mode": "test_only" if sparse else "supported",
        }
        if efficiency is None:
            rows.append(_unavailable_row(role, root, month, module, "city_content_efficiency_unavailable", scope, sample_size=sample_size))
            continue
        rows.append(_row(role, root, month, module, "city_content_efficiency", efficiency, comparison={"notes": note_count} if note_count is not None else None, scope=scope, sample_size=sample_size, confidence=confidence))
        for category in content.get("categories", []):
            if not isinstance(category, dict) or not _finite(category.get("reads_per_note")):
                continue
            rows.append(_row(role, root, month, module, "city_category_efficiency", category["reads_per_note"], scope={**scope, "category": category.get("category", "unclassified")}, sample_size=sample_size, confidence=confidence))
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
    scoped_rows = _business_opportunity_rows(role, root, month, module)
    return _or_placeholder(role, root, month, module, scoped_rows)


def _business_opportunity_rows(role: str, root: dict, month: str, module: str) -> list[dict]:
    rows: list[dict] = []
    scenarios = (
        ("trade_in", ("trade", "\u7f6e\u6362", "\u4e8c\u624b")),
        ("local_service", ("service", "\u670d\u52a1", "\u672c\u5730")),
        ("installment_value", ("installment", "\u5206\u671f", "\u4ef7\u503c", "\u6027\u4ef7\u6bd4")),
        ("women", ("women", "\u5973\u6027", "\u5973\u751f")),
        ("student", ("student", "\u5b66\u751f")),
    )
    for cohort, region, categories, evidence_basis in _business_scope_groups(role, root):
        total_notes = sum(_number(item.get("notes")) or 0 for item in categories)
        total_reads = sum(_number(item.get("reads")) or 0 for item in categories)
        if not categories or (not total_notes and not total_reads):
            continue
        for scenario, terms in scenarios:
            matches = [item for item in categories if any(term in str(item.get("category", "")).lower() for term in terms)]
            demand = sum(_number(item.get("reads")) or 0 for item in matches) / total_reads if total_reads else 0
            supply = sum(_number(item.get("notes")) or 0 for item in matches) / total_notes if total_notes else 0
            concentration = sum(value ** 2 for value in _category_share_map(matches).values())
            scope = {"scenario": scenario, "revalidation_required": True, "cohort": cohort, "evidence_basis": evidence_basis}
            if region:
                scope["region"] = region
            rows.append(_row(role, root, month, module, "scenario_demand_share", demand, comparison={"supply_share": supply, "supply_gap": demand - supply, "competition_concentration": concentration}, scope=scope, sample_size=_int(sum(_number(item.get("notes")) or 0 for item in matches)), confidence="validate"))
    return rows


def _business_scope_groups(role: str, root: dict) -> list[tuple[str, str, list[dict], str]]:
    if role == "dealer" and _mapping(root.get("content_by_cohort")):
        return [
            (str(cohort), "", [item for item in _mapping(content).get("categories", []) if isinstance(item, dict)], "content_by_cohort")
            for cohort, content in sorted(_mapping(root.get("content_by_cohort")).items())
            if isinstance(content, dict)
        ]
    if role == "apple":
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for category in _categories(role, root):
            grouped[(str(category.get("cohort", "all_scoped_accounts")), str(category.get("region", "")))].append(category)
        if grouped:
            return [(cohort, region, categories, "cohort_region_category_aggregate") for (cohort, region), categories in sorted(grouped.items())]
    return [("all_scoped_accounts", "", _categories(role, root), "aggregate_content_summary")]


def _dealer_matrix_rows(root: dict, month: str) -> list[dict]:
    rows: list[dict] = []
    accounts = _account_rows("dealer", root)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for account in accounts:
        cohort = str(account.get("cohort", "expanded_store"))
        metrics = _mapping(account.get("metrics"))
        reads, notes = _number(metrics.get("reads")), _number(metrics.get("notes"))
        if reads is None or notes is None or notes <= 0:
            rows.append(_unavailable_row("dealer", root, month, "matrix_health", "account_matrix_unavailable", {"cohort": cohort, "account_id": str(account.get("author_id", "unidentified")), "evidence_basis": "account_reads_and_notes"}))
            continue
        grouped[cohort].append({"account": account, "reads": reads, "notes": notes, "reads_per_note": reads / notes})
    for cohort, members in sorted(grouped.items()):
        supply_median = median(item["notes"] for item in members)
        efficiency_median = median(item["reads_per_note"] for item in members)
        for item in members:
            account = item["account"]
            quadrant = ("high_supply" if item["notes"] >= supply_median else "low_supply") + "_" + ("high_efficiency" if item["reads_per_note"] >= efficiency_median else "low_efficiency")
            tier = "S" if item["reads_per_note"] >= efficiency_median * 1.5 else "A" if item["reads_per_note"] >= efficiency_median else "B" if item["reads_per_note"] >= efficiency_median * 0.5 else "C"
            account_id = str(account.get("author_id", "unidentified"))
            rows.append(_row("dealer", root, month, "matrix_health", "account_quadrant", 1, scope={"cohort": cohort, "account_id": account_id, "quadrant": quadrant}, sample_size=len(members)))
            rows.append(_row("dealer", root, month, "matrix_health", "tier_candidate", 1, scope={"cohort": cohort, "account_id": account_id, "tier": tier}, sample_size=len(members)))
        rows.append(_row("dealer", root, month, "matrix_health", "posting_frequency", sum(item["notes"] for item in members) / len(members), scope={"cohort": cohort, "unit": "notes_per_account", "evidence_basis": "accounts_with_valid_notes"}, sample_size=len(members)))
    return rows


def _add_note_long_tail_evidence(role: str, root: dict, month: str, module: str, ranked_notes: list[tuple[dict, float]], rows: list[dict], cohort: str) -> None:
    if not ranked_notes:
        rows.append(_unavailable_row(role, root, month, module, "long_tail_candidates_unavailable", {"pattern_type": "long_tail", "evidence_basis": "note_rows", "cohort": cohort}))
        return
    threshold = median(reads for _, reads in ranked_notes)
    candidates = [(rank, note, reads) for rank, (note, reads) in enumerate(ranked_notes, start=1) if reads < threshold]
    rows.append(_row(role, root, month, module, "long_tail_note_candidate_count", len(candidates), scope={"pattern_type": "long_tail", "evidence_basis": "note_rows", "threshold_reads": threshold, "cohort": cohort}, sample_size=len(ranked_notes)))
    for rank, note, reads in candidates:
        scope = {"pattern_type": "long_tail", "evidence_basis": "note_rows", "note_id": _note_id(note), "note_rank": rank, "cohort": cohort}
        rows.append(_row(role, root, month, module, "long_tail_note_reads", reads, scope=scope, sample_size=len(ranked_notes)))
        age_days = _note_age_days(note, month)
        if age_days is None:
            rows.append(_unavailable_row(role, root, month, module, "long_tail_age_unavailable", scope, sample_size=len(ranked_notes)))
        else:
            rows.append(_row(role, root, month, module, "long_tail_age_days", age_days, scope=scope, sample_size=len(ranked_notes)))


def _account_user_signal_rows(role: str, root: dict, month: str, module: str, cohort: str, accounts: list[dict], include_account_candidates: bool) -> list[dict]:
    rows: list[dict] = []
    values = {
        metric: sum(_number(_mapping(account.get("metrics")).get(metric)) or 0 for account in accounts)
        for metric in ("reads", "likes", "collects", "comments", "shares", "new_fans")
    }
    scope = {"cohort": cohort, "evidence_basis": "account_metrics"}
    if values["reads"]:
        for metric in ("likes", "collects", "comments", "shares"):
            rows.append(_row(role, root, month, module, metric + "_per_read", values[metric] / values["reads"], scope={**scope, "signal": metric}, sample_size=len(accounts)))
        rows.append(_row(role, root, month, module, "fans_per_read", values["new_fans"] / values["reads"], scope={**scope, "signal": "fan_conversion"}, sample_size=len(accounts)))
    if include_account_candidates:
        for metric, label in (("collects", "high_save"), ("comments", "high_comment")):
            observed = [_number(_mapping(account.get("metrics")).get(metric)) or 0 for account in accounts]
            cutoff = median(observed)
            rows.append(_row(role, root, month, module, label + "_candidate_count", sum(value > cutoff for value in observed), scope={**scope, "signal": label, "candidate_unit": "account"}, sample_size=len(accounts)))
        anomaly_count = sum((_number(_mapping(account.get("metrics")).get("reads")) or 0) == 0 and sum((_number(_mapping(account.get("metrics")).get(metric)) or 0) for metric in ("likes", "collects", "comments")) > 0 for account in accounts)
        rows.append(_row(role, root, month, module, "anomaly_candidate_count", anomaly_count, scope={**scope, "signal": "interactions_without_reads", "candidate_unit": "account"}, sample_size=len(accounts)))
    return rows


def _add_note_user_candidates(role: str, root: dict, month: str, module: str, notes: list[dict], rows: list[dict], cohort: str) -> None:
    for metric, label in (("collects", "high_save"), ("comments", "high_comment")):
        observed = [(note, _number(note.get(metric))) for note in notes]
        observed = [(note, value) for note, value in observed if value is not None]
        if not observed:
            rows.append(_unavailable_row(role, root, month, module, label + "_candidates_unavailable", {"signal": label, "candidate_unit": "note", "evidence_basis": "note_rows", "cohort": cohort}, sample_size=len(notes)))
            continue
        cutoff = median(value for _, value in observed)
        candidates = sorted(((note, value) for note, value in observed if value > cutoff), key=lambda item: (-item[1], _note_id(item[0])))
        rows.append(_row(role, root, month, module, label + "_note_candidate_count", len(candidates), comparison={"median": cutoff}, scope={"signal": label, "candidate_unit": "note", "evidence_basis": "note_rows", "cohort": cohort}, sample_size=len(observed)))
        for rank, (note, value) in enumerate(candidates, start=1):
            rows.append(_row(role, root, month, module, label + "_note_candidate", value, comparison={"median": cutoff}, scope={"signal": label, "candidate_unit": "note", "evidence_basis": "note_rows", "note_id": _note_id(note), "note_rank": rank, "cohort": cohort}, sample_size=len(observed)))


def _apple_matrix_rows(root: dict, month: str) -> list[dict]:
    rows: list[dict] = []
    quadrants = [item for item in _mapping(root).get("dealer_quadrants", []) if isinstance(item, dict)]
    tier_by_quadrant = {
        "high_supply_high_efficiency": "S",
        "low_supply_high_efficiency": "A",
        "high_supply_low_efficiency": "B",
        "low_supply_low_efficiency": "C",
    }
    valid_quadrants = [
        item for item in quadrants
        if (
            str(item.get("quadrant")) in tier_by_quadrant
            and (notes := _number(item.get("notes"))) is not None
            and notes > 0
            and _number(item.get("reads_per_note")) is not None
        )
    ]
    for item in quadrants:
        if item not in valid_quadrants:
            rows.append(_unavailable_row("apple", root, month, "matrix_health", "dealer_quadrant_unavailable", {"cohort": str(item.get("cohort", "expanded_store")), "quadrant": str(item.get("quadrant", "unclassified")), "evidence_basis": "known_quadrant_with_finite_notes_and_reads_per_note"}))
    counts = Counter(str(item.get("quadrant", "unclassified")) for item in valid_quadrants)
    for quadrant, count in sorted(counts.items()):
        rows.append(_row("apple", root, month, "matrix_health", "quadrant_distribution", count, scope={"quadrant": quadrant, "cohort": "network", "evidence_basis": "valid_dealer_quadrants"}, sample_size=len(valid_quadrants)))
    account_counts = _mapping(root).get("account_counts", {})
    by_cohort: dict[str, list[dict]] = defaultdict(list)
    for item in valid_quadrants:
        by_cohort[str(item.get("cohort", "expanded_store"))].append(item)
    for cohort, members in sorted(by_cohort.items()):
        account_count = _int(_mapping(account_counts).get(cohort))
        notes = [_number(item.get("notes")) for item in members]
        if account_count and all(value is not None for value in notes):
            rows.append(_row("apple", root, month, "matrix_health", "network_posting_frequency", sum(notes) / account_count, scope={"cohort": cohort, "unit": "notes_per_account"}, sample_size=account_count))
        tiers = Counter(tier_by_quadrant[str(item.get("quadrant"))] for item in members)
        for tier, count in sorted(tiers.items()):
            rows.append(_row("apple", root, month, "matrix_health", "tier_candidate_count", count, scope={"tier": tier, "cohort": cohort, "basis": "dealer_quadrant"}, sample_size=len(members)))
    return rows


def _category_share_similarity_rows(role: str, root: dict, month: str) -> list[dict]:
    rows: list[dict] = []
    if role == "dealer":
        for cohort, summary in sorted(_mapping(root.get("content_by_cohort")).items()):
            categories = [item for item in _mapping(summary).get("categories", []) if isinstance(item, dict)]
            actual = _category_share_map(categories)
            benchmark = {
                str(item.get("category", "unclassified")): _number(item.get("benchmark_note_share"))
                for item in categories
                if _number(item.get("benchmark_note_share")) is not None
            }
            similarity = _cosine_similarity(actual, benchmark)
            if similarity is not None:
                rows.append(_row("dealer", root, month, "matrix_health", "category_share_similarity", similarity, scope={"cohort": cohort, "comparison_scope": "same_cohort_benchmark"}, sample_size=len(actual)))
        return rows

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for category in _categories("apple", root):
        grouped[(str(category.get("region", "unassigned")), str(category.get("cohort", "expanded_store")))].append(category)
    cohort_totals: dict[str, Counter] = defaultdict(Counter)
    for (_, cohort), categories in grouped.items():
        for name, value in _category_count_map(categories).items():
            cohort_totals[cohort][name] += value
    for (region, cohort), categories in sorted(grouped.items()):
        similarity = _cosine_similarity(_category_share_map(categories), _normalize_counts(cohort_totals[cohort]))
        if similarity is not None:
            rows.append(_row("apple", root, month, "matrix_health", "category_share_similarity", similarity, scope={"region": region, "cohort": cohort, "comparison_scope": "network_cohort_distribution"}, sample_size=len(categories)))
    return rows


def _category_count_map(categories: list[dict]) -> dict[str, float]:
    return {
        str(item.get("category", "unclassified")): _number(item.get("notes")) or 0
        for item in categories
    }


def _category_share_map(categories: list[dict]) -> dict[str, float]:
    direct = {
        str(item.get("category", "unclassified")): _number(item.get("note_share"))
        for item in categories
        if _number(item.get("note_share")) is not None
    }
    return direct if direct else _normalize_counts(_category_count_map(categories))


def _normalize_counts(counts: dict[str, float]) -> dict[str, float]:
    total = sum(counts.values())
    return {name: value / total for name, value in counts.items()} if total else {}


def _cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float | None:
    names = sorted(set(left) | set(right))
    if not names:
        return None
    dot = sum(left.get(name, 0) * right.get(name, 0) for name in names)
    left_norm = math.sqrt(sum(left.get(name, 0) ** 2 for name in names))
    right_norm = math.sqrt(sum(right.get(name, 0) ** 2 for name in names))
    return dot / (left_norm * right_norm) if left_norm and right_norm else None


def _apple_city_segments(payload: dict, root: dict) -> list[dict]:
    summaries = [item for item in _mapping(root).get("city_summaries", []) if isinstance(item, dict)]
    summary_counts = {str(item.get("city", "unassigned")): _int(item.get("account_count")) for item in summaries}
    grouped: dict[tuple[str, str, str], dict] = {}
    account_content: dict[tuple[str, str, str], dict] = {}
    explicit_accounts = root.get("accounts") if isinstance(root.get("accounts"), list) else payload.get("accounts", [])
    for account in explicit_accounts:
        if not isinstance(account, dict):
            continue
        city = str(account.get("city", "unassigned"))
        region = str(account.get("region", "unassigned"))
        cohort = str(account.get("cohort", "expanded_store"))
        metrics = _mapping(account.get("metrics"))
        reads, notes = _number(metrics.get("reads")), _number(metrics.get("notes"))
        if reads is None or notes is None:
            continue
        item = account_content.setdefault((city, region, cohort), {"city": city, "region": region, "cohort": cohort, "account_count": 0, "content": {"notes": 0.0, "reads": 0.0, "categories": []}})
        item["account_count"] += 1
        item["content"]["notes"] += notes
        item["content"]["reads"] += reads
    for dealer in payload.get("dealers", []):
        if not isinstance(dealer, dict):
            continue
        accounts = [item for item in dealer.get("accounts", []) if isinstance(item, dict)]
        account_counts = Counter((str(item.get("city", "unassigned")), str(item.get("region", "unassigned")), str(item.get("cohort", "expanded_store"))) for item in accounts)
        for segment in _mapping(dealer.get("content")).get("by_city_cohort", []):
            if not isinstance(segment, dict):
                continue
            city = str(segment.get("city", "unassigned"))
            region = str(segment.get("region", "unassigned"))
            cohort = str(segment.get("cohort", "expanded_store"))
            content = _mapping(segment.get("content"))
            notes, reads = _number(content.get("notes")), _number(content.get("reads"))
            if notes is None or reads is None:
                continue
            item = grouped.setdefault((city, region, cohort), {"city": city, "region": region, "cohort": cohort, "account_count": 0, "content": {"notes": 0.0, "reads": 0.0, "categories": []}})
            item["account_count"] += account_counts[(city, region, cohort)]
            item["content"]["notes"] += notes
            item["content"]["reads"] += reads
            item["content"]["categories"].extend(category for category in content.get("categories", []) if isinstance(category, dict))
    for key, item in account_content.items():
        grouped.setdefault(key, item)
    result = list(grouped.values())
    for item in result:
        notes = item["content"]["notes"]
        item["content"]["reads_per_note"] = item["content"]["reads"] / notes if notes else None
        if not item["account_count"]:
            item["account_count"] = summary_counts.get(item["city"])
    represented = {item["city"] for item in result}
    result.extend({"city": city, "region": "unassigned", "cohort": "all_scoped_accounts", "account_count": count, "content": {}} for city, count in summary_counts.items() if city not in represented)
    return sorted(result, key=lambda item: (item["city"], item["region"], item["cohort"]))


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
        "quality_status": _quality_status(payload, root),
    }


def _root(role: str, payload: dict) -> dict:
    return _mapping(payload.get(role)) if isinstance(payload.get(role), dict) else _mapping(payload)


def _quality_status(payload: dict, root: dict) -> str:
    return str(
        _mapping(payload.get("quality")).get("quality_status")
        or _mapping(root.get("quality")).get("quality_status")
        or "unknown"
    )


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


def _content_scopes(role: str, root: dict) -> list[tuple[str, dict, list[dict], str]]:
    if role == "dealer":
        by_cohort = _mapping(root.get("content_by_cohort"))
        if by_cohort:
            return [
                (str(cohort), _mapping(content), [item for item in _mapping(content).get("categories", []) if isinstance(item, dict)], "content_by_cohort")
                for cohort, content in sorted(by_cohort.items())
                if isinstance(content, dict)
            ]
    if role == "apple":
        grouped: dict[str, list[dict]] = defaultdict(list)
        for category in _categories(role, root):
            cohort = category.get("cohort")
            if cohort:
                grouped[str(cohort)].append(category)
        if grouped:
            return [
                (cohort, _content_from_categories(categories), categories, "cohort_category_aggregate")
                for cohort, categories in sorted(grouped.items())
            ]
    content = _content(role, root)
    return [("all_scoped_accounts", content, _categories(role, root), "aggregate_content_summary")]


def _content_from_categories(categories: list[dict]) -> dict:
    values = {"notes": 0.0, "reads": 0.0, "interactions": 0.0, "new_fans": 0.0}
    for category in categories:
        for metric in values:
            values[metric] += _number(category.get(metric)) or 0
    values["reads_per_note"] = values["reads"] / values["notes"] if values["notes"] else None
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


def _notes_for_cohort(notes: list[dict], cohort: str, scope_count: int) -> list[dict]:
    if cohort == "all_scoped_accounts" or scope_count == 1:
        return notes
    return [note for note in notes if str(note.get("cohort", "")) == cohort]


def _ranked_notes_by_reads(notes: list[dict]) -> list[tuple[dict, float]]:
    return sorted(
        ((note, reads) for note in notes if (reads := _number(note.get("reads"))) is not None),
        key=lambda item: (-item[1], _note_id(item[0])),
    )


def _note_reads_coverage(notes: list[dict]) -> dict[str, int]:
    return {"observed": sum(_number(note.get("reads")) is not None for note in notes), "total": len(notes)}


def _note_reads_are_complete(notes: list[dict]) -> bool:
    coverage = _note_reads_coverage(notes)
    return coverage["total"] > 0 and coverage["observed"] == coverage["total"]


def _top_20_note_read_share(notes: list[dict]) -> float | None:
    ranked = _ranked_notes_by_reads(notes)
    total_reads = sum(reads for _, reads in ranked)
    return sum(reads for _, reads in ranked[:20]) / total_reads if total_reads else None


def _note_id(note: dict) -> str:
    return str(note.get("note_id") or note.get("id") or "unidentified-note")


def _fiscal_quarter_key(value: Any) -> str:
    quarter = str(value or "").upper()
    return quarter.lower() if re.fullmatch(r"Q[1-4]", quarter) else "fiscal"


def _city_segments(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root.get("content")).get("by_city_cohort", []) if isinstance(item, dict)]
    return [item for item in _mapping(root).get("city_summaries", []) if isinstance(item, dict)]


def _city_account_count(role: str, root: dict, city: Any, cohort: Any = None) -> int:
    if role != "dealer":
        return 0
    return sum(
        item.get("city") == city and (cohort in (None, "") or item.get("cohort") == cohort)
        for item in _account_rows(role, root)
    )


def _actions(role: str, root: dict) -> list[dict]:
    if role == "dealer":
        return [item for item in _mapping(root).get("recommendations", []) if isinstance(item, dict)]
    actions = []
    for bucket in _mapping(root).get("actions", {}).values():
        if isinstance(bucket, list):
            actions.extend(item for item in bucket if isinstance(item, dict))
    return actions


def _row(role: str, root: dict, month: str, module: str, metric: str, value: Any, *, comparison: Any = None, scope: dict | None = None, sample_size: int | None = None, confidence: str = "supported") -> dict:
    return evidence(_evidence_id(role, root, month, module, scope or {}, metric), module, metric, value, comparison=comparison, scope=scope, sample_size=sample_size, confidence=confidence)


def _unavailable_row(role: str, root: dict, month: str, module: str, metric: str, scope: dict | None = None, *, sample_size: int | None = None) -> dict:
    return _row(role, root, month, module, metric, 0, scope={**(scope or {}), "availability": "insufficient_data"}, sample_size=sample_size, confidence="validate")


def _or_placeholder(role: str, root: dict, month: str, module: str, rows: list[dict]) -> list[dict]:
    if rows:
        return rows
    return [_row(role, root, month, module, "insufficient_data", 0, scope={"availability": "insufficient_data"}, confidence="validate")]


def _evidence_id(role: str, root: dict, month: str, module: str, scope: dict, metric: str) -> str:
    if role == "dealer":
        subject = str(root.get("dealer_id", "unknown-dealer"))
        prefix = f"dealer:{subject}:{month}"
    else:
        prefix = f"apple:{month}"
    parts = [str(scope[key]) for key in ("cohort", "city", "region", "category", "account_id", "note_id", "note_rank", "token", "scenario", "horizon_days", "quadrant", "tier", "pattern_type", "format") if scope.get(key) not in (None, "")]
    return ":".join([prefix, module, *parts, metric])


def _with_unique_evidence_ids(rows: list[dict]) -> list[dict]:
    occurrences: dict[str, int] = defaultdict(int)
    for row in rows:
        evidence_id = row["evidence_id"]
        occurrences[evidence_id] += 1
        if occurrences[evidence_id] > 1:
            row["evidence_id"] = evidence_id + ":" + str(occurrences[evidence_id])
    return rows


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


def _hotspot_recency(notes: list[dict], month: str) -> int | None:
    if not notes:
        return None
    dates = [date for note in notes if (date := _note_date(note)) is not None]
    if not dates:
        return None
    snapshot = _month_end(month)
    if snapshot is None:
        return None
    return max(0, (snapshot - max(dates)).days)


def _note_age_days(note: dict, month: str) -> int | None:
    date, snapshot = _note_date(note), _month_end(month)
    return max(0, (snapshot - date).days) if date is not None and snapshot is not None else None


def _note_date(note: dict) -> datetime | None:
    value = str(note.get("publish_date", note.get("published_at", "")))[:10]
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _month_end(month: str) -> datetime | None:
    try:
        year, month_number = (int(part) for part in month.split("-", 1))
        return datetime(year, month_number, monthrange(year, month_number)[1])
    except ValueError:
        return None


def _title_tokens(notes: list[dict]) -> Counter:
    tokens: Counter = Counter()
    for note in notes:
        tokens.update(token.lower() for token in re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]{2,}", str(note.get("title", ""))))
    return tokens


def _top_tokens(tokens: Counter, limit: int = 10) -> list[tuple[str, int]]:
    return sorted(tokens.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _top_token(tokens: Counter) -> str:
    return _top_tokens(tokens, 1)[0][0]


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
