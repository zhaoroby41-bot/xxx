"""Strict validation for AI-generated insight artifacts."""

from __future__ import annotations

import copy
import json
import math
import re
from typing import Any


ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_STATEMENT_TYPES = {"fact", "inference", "recommendation"}
REQUIRED_MODULES = {
    "growth_diagnosis",
    "matrix_health",
    "content_patterns",
    "user_signals",
    "regional_strategy",
    "action_plan",
    "business_opportunities",
}

_TOP_LEVEL_FIELDS = {"executive_summary", "insights", "generation"}
_INSIGHT_FIELDS = {
    "id", "module", "title", "judgement", "why", "impact",
    "statement_type", "evidence_ids", "confidence", "scope", "actions",
}
_ACTION_FIELDS = {"owner", "action", "deadline", "success_metric"}
_NUMBER_PATTERN = re.compile(r"([+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+))\s*(%)?")


class AIContractError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_ai_result(result: dict, packet: dict, allowed_entity_ids: set[str]) -> dict:
    """Validate raw model output and return an independent normalized copy."""
    errors: list[str] = []
    if not isinstance(result, dict):
        raise AIContractError(["invalid_result"])
    if not isinstance(packet, dict):
        raise AIContractError(["invalid_packet"])

    _validate_finite_values(result, errors)
    _validate_top_level(result, errors)
    evidence_by_id = _evidence_by_id(packet, errors)
    insights = result.get("insights")
    if isinstance(insights, list):
        for insight in insights:
            _validate_insight(insight, evidence_by_id, allowed_entity_ids, errors)
    _validate_module_coverage(insights, packet.get("module_status"), errors)
    if errors:
        raise AIContractError(_unique(errors))
    return _normalize_result(result)


def _validate_top_level(result: dict, errors: list[str]) -> None:
    for field in _TOP_LEVEL_FIELDS:
        if field not in result:
            errors.append("missing_top_level")
    if "executive_summary" in result and not _non_empty_string(result["executive_summary"]):
        errors.append("invalid_top_level")
    if "generation" in result and not isinstance(result["generation"], dict):
        errors.append("invalid_top_level")
    if "insights" in result and not isinstance(result["insights"], list):
        errors.append("invalid_insights")


def _evidence_by_id(packet: dict, errors: list[str]) -> dict[str, dict]:
    evidence = packet.get("evidence")
    if not isinstance(evidence, list):
        errors.append("invalid_packet_evidence")
        return {}
    rows: dict[str, dict] = {}
    for row in evidence:
        if not isinstance(row, dict) or not isinstance(row.get("evidence_id"), str):
            errors.append("invalid_packet_evidence")
            continue
        rows[row["evidence_id"]] = row
    return rows


def _validate_insight(insight: Any, evidence_by_id: dict[str, dict], allowed_entity_ids: set[str], errors: list[str]) -> None:
    if not isinstance(insight, dict):
        errors.append("invalid_insight")
        return
    missing_fields = _INSIGHT_FIELDS - set(insight)
    if missing_fields:
        errors.append("incomplete_insight")
    for field in ("id", "module", "title", "judgement", "why", "impact", "statement_type", "confidence"):
        if field in insight and not _non_empty_string(insight.get(field)):
            errors.append("invalid_insight_field")
    module = insight.get("module")
    if module not in REQUIRED_MODULES:
        errors.append("invalid_module")
    if insight.get("statement_type") not in ALLOWED_STATEMENT_TYPES:
        errors.append("invalid_statement_type")
    if insight.get("confidence") not in ALLOWED_CONFIDENCE:
        errors.append("invalid_confidence")

    linked_rows = _validate_evidence_links(insight.get("evidence_ids"), module, evidence_by_id, errors)
    _validate_numbers(insight, linked_rows, errors)
    _validate_scope_entities(insight.get("scope"), allowed_entity_ids, errors)
    _validate_actions(insight.get("actions"), allowed_entity_ids, errors)


def _validate_evidence_links(evidence_ids: Any, module: Any, evidence_by_id: dict[str, dict], errors: list[str]) -> list[dict]:
    if not isinstance(evidence_ids, list) or not all(isinstance(value, str) for value in evidence_ids):
        errors.append("invalid_evidence_ids")
        return []
    if not evidence_ids:
        errors.append("missing_evidence")
        return []
    linked_rows: list[dict] = []
    for evidence_id in evidence_ids:
        row = evidence_by_id.get(evidence_id)
        if row is None:
            errors.append("unknown_evidence")
            continue
        if row.get("module") != module:
            errors.append("cross_module_evidence")
            continue
        linked_rows.append(row)
    return linked_rows


def _validate_numbers(insight: dict, linked_rows: list[dict], errors: list[str]) -> None:
    supported = [number for row in linked_rows for number in _evidence_numbers(row)]
    for field in ("judgement", "why", "impact"):
        value = insight.get(field)
        if not isinstance(value, str):
            errors.append("invalid_insight_text")
            continue
        for number, is_percent in _text_numbers(value):
            expected_values = (number / 100, number) if is_percent else (number,)
            # Percentages in the UI are deliberately rounded to one decimal place.
            abs_tolerance = 0.001 if is_percent else 1e-9
            if not any(
                math.isclose(expected, candidate, rel_tol=1e-9, abs_tol=abs_tolerance)
                for expected in expected_values
                for candidate in supported
            ):
                errors.append("unsupported_number")


def _evidence_numbers(row: dict) -> list[float]:
    numbers: list[float] = []
    for field in ("value", "comparison", "sample_size", "scope"):
        numbers.extend(_finite_numbers(row.get(field)))
    return numbers


def _finite_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)] if math.isfinite(value) else []
    if isinstance(value, dict):
        return [number for item in value.values() for number in _finite_numbers(item)]
    if isinstance(value, (list, tuple)):
        return [number for item in value for number in _finite_numbers(item)]
    return []


def _text_numbers(value: str) -> list[tuple[float, bool]]:
    return [(float(match.group(1).replace(",", "")), bool(match.group(2))) for match in _NUMBER_PATTERN.finditer(value)]


def _validate_scope_entities(scope: Any, allowed_entity_ids: set[str], errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("invalid_scope")
        return
    entity_ids = scope.get("entity_ids")
    if entity_ids is None:
        return
    if not isinstance(entity_ids, list) or not all(isinstance(value, str) for value in entity_ids):
        errors.append("invalid_scope")
        return
    if any(entity_id not in allowed_entity_ids for entity_id in entity_ids):
        errors.append("unknown_entity")


def _validate_actions(actions: Any, allowed_entity_ids: set[str], errors: list[str]) -> None:
    if not isinstance(actions, list):
        errors.append("invalid_actions")
        return
    for action in actions:
        if (
            not isinstance(action, dict)
            or any(not _non_empty_string(action.get(field)) for field in _ACTION_FIELDS)
        ):
            errors.append("incomplete_action")
            continue
        if "scope" in action:
            _validate_scope_entities(action["scope"], allowed_entity_ids, errors)


def _validate_module_coverage(insights: Any, module_status: Any, errors: list[str]) -> None:
    if not isinstance(module_status, dict):
        errors.append("invalid_module_status")
        return
    if set(module_status) != REQUIRED_MODULES:
        errors.append("invalid_module_status")
    present_modules = {
        insight.get("module") for insight in insights
        if isinstance(insight, dict) and insight.get("module") in REQUIRED_MODULES
    } if isinstance(insights, list) else set()
    for module, status in module_status.items():
        if module in REQUIRED_MODULES and status == "ready" and module not in present_modules:
            errors.append("missing_ready_module_insight")
        if module in REQUIRED_MODULES and status == "insufficient_data":
            for insight in insights if isinstance(insights, list) else []:
                if isinstance(insight, dict) and insight.get("module") == module and insight.get("confidence") != "low":
                    errors.append("insufficient_data_requires_low_confidence")


def _validate_finite_values(value: Any, errors: list[str]) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        errors.append("non_finite_number")
    elif isinstance(value, dict):
        for item in value.values():
            _validate_finite_values(item, errors)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _validate_finite_values(item, errors)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _unique(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _normalize_result(result: dict) -> dict:
    """Return an independent JSON-normalized value with finite numbers only."""
    try:
        return json.loads(json.dumps(copy.deepcopy(result), ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise AIContractError(["non_json_value"]) from error
