"""Evidence-bound AI insight generation with an offline deterministic fallback."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Mapping

from .ai_contract import validate_ai_result
from .insight_evidence import REQUIRED_MODULES


_PROMPT_PATH = Path(__file__).resolve().parents[1] / "config" / "ai_prompt.json"


def load_prompt() -> dict:
    """Load the versioned prompt as strict JSON."""
    with _PROMPT_PATH.open("r", encoding="utf-8") as source:
        return json.load(source)


def generate_ai_insights(
    packet: dict,
    *,
    cache_path: Path,
    env: Mapping[str, str],
    transport=None,
) -> dict:
    """Generate validated insights without modifying the evidence packet."""
    scope = packet.get("data_scope") if isinstance(packet.get("data_scope"), dict) else {}
    raw_entity_ids = scope.get("allowed_entity_ids", [])
    allowed_entity_ids = set(raw_entity_ids) if isinstance(raw_entity_ids, (list, tuple, set)) else set()
    has_provider_config = bool(env.get("INSIGHT_AI_API_KEY") and env.get("INSIGHT_AI_MODEL"))

    if has_provider_config:
        try:
            result = validate_ai_result(
                _provider_request(packet, load_prompt(), env, transport), packet, allowed_entity_ids
            )
            result["generation"].update({"mode": "ai", "model": env["INSIGHT_AI_MODEL"]})
            _write_cache(cache_path, packet, result)
            return _json_copy(result)
        except Exception:
            # Provider output is untrusted; a valid scoped cache is preferable to new rules.
            cached = _read_valid_same_period_cache(cache_path, packet, allowed_entity_ids)
            if cached is not None:
                cached["generation"]["mode"] = "cached_ai"
                return cached
    else:
        cached = _read_valid_same_period_cache(cache_path, packet, allowed_entity_ids)
        if cached is not None:
            cached["generation"]["mode"] = "cached_ai"
            return cached

    result = validate_ai_result(build_rule_fallback(packet), packet, allowed_entity_ids)
    result["generation"]["mode"] = "rule_fallback"
    return _json_copy(result)


def _provider_request(packet: dict, prompt: dict, env: Mapping[str, str], transport=None) -> dict:
    role = packet.get("role")
    if role not in prompt.get("roles", {}):
        raise ValueError("packet role is not configured in prompt")
    base_url = env.get("INSIGHT_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": env["INSIGHT_AI_MODEL"],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "system", "content": prompt["roles"][role]},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, allow_nan=False)},
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {env['INSIGHT_AI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    response = (transport or urllib.request.urlopen)(request, timeout=90)
    payload = json.loads(response.read().decode("utf-8"))
    return json.loads(payload["choices"][0]["message"]["content"])


def _write_cache(cache_path: Path, packet: dict, result: dict) -> None:
    envelope = {
        "cache_version": 1,
        "role": packet.get("role"),
        "calendar_month": packet.get("period", {}).get("calendar_month"),
        "result": result,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(envelope, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


def _read_valid_same_period_cache(cache_path: Path, packet: dict, allowed_entity_ids: set[str]) -> dict | None:
    try:
        envelope = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict):
            return None
        if envelope.get("role") != packet.get("role"):
            return None
        if envelope.get("calendar_month") != packet.get("period", {}).get("calendar_month"):
            return None
        return validate_ai_result(envelope.get("result"), packet, allowed_entity_ids)
    except (OSError, TypeError, ValueError):
        return None


def build_rule_fallback(packet: dict) -> dict:
    """Produce one conservative, evidence-linked insight for each available module."""
    evidence_by_module: dict[str, list[dict]] = {module: [] for module in REQUIRED_MODULES}
    for row in packet.get("evidence", []):
        if isinstance(row, dict) and row.get("module") in evidence_by_module and row.get("evidence_id"):
            evidence_by_module[row["module"]].append(row)

    statuses = packet.get("module_status", {})
    insights = []
    for module in REQUIRED_MODULES:
        rows = evidence_by_module[module]
        if not rows:
            continue
        ready = statuses.get(module) == "ready"
        selected = next(
            (row for row in rows if row.get("scope", {}).get("availability") != "insufficient_data"), rows[0]
        )
        metric = str(selected.get("metric") or "当前证据")
        if ready:
            judgement = f"数据显示，{metric}值得持续跟踪。"
            why = "该判断仅基于当前已链接证据，建议结合后续周期验证。"
            impact = "建议将该信号纳入本期运营复盘。"
            confidence = "medium"
            statement_type = "inference"
        else:
            judgement = f"当前{metric}的可用证据有限。"
            why = "数据显示资料不足，建议验证后再形成明确判断。"
            impact = "建议优先补充该模块所需的观察资料。"
            confidence = "low"
            statement_type = "recommendation"
        insights.append({
            "id": f"rule-{module}",
            "module": module,
            "title": f"{module} 观察",
            "judgement": judgement,
            "why": why,
            "impact": impact,
            "statement_type": statement_type,
            "evidence_ids": [selected["evidence_id"]],
            "confidence": confidence,
            "scope": {},
            "actions": [{
                "owner": "渠道运营",
                "action": "复核证据并安排下一步验证",
                "deadline": "下一周期",
                "success_metric": "形成可复核的模块结论",
            }],
        })
    return {
        "executive_summary": "本报告基于已提供证据生成，建议在后续周期继续验证。",
        "generation": {"mode": "rule_fallback", "provider": "deterministic_rules"},
        "insights": insights,
    }


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
