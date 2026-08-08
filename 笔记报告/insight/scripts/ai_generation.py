"""Evidence-bound AI insight generation with an offline deterministic fallback."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Mapping

try:
    from .ai_contract import validate_ai_result
    from .insight_evidence import REQUIRED_MODULES
except ImportError:  # pragma: no cover - keeps direct script execution working.
    from ai_contract import validate_ai_result
    from insight_evidence import REQUIRED_MODULES


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
            raw = _strip_secrets(_provider_request(packet, load_prompt(), env, transport), _env_secrets(env))
            result = validate_ai_result(raw, packet, allowed_entity_ids)
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
        selected = _select_fallback_evidence(rows)
        if ready:
            judgement = "\u6570\u636e\u8bc1\u636e\u663e\u793a\u5f53\u524d\u6a21\u5757\u5b58\u5728\u53ef\u8ddf\u8fdb\u4fe1\u53f7\u3002"
            why = "\u8be5\u5224\u65ad\u4ec5\u57fa\u4e8e\u5f53\u524d\u5df2\u94fe\u63a5\u8bc1\u636e\uff0c\u9700\u8981\u7ed3\u5408\u540e\u7eed\u5468\u671f\u9a8c\u8bc1\u3002"
            impact = "\u5efa\u8bae\u5c06\u8be5\u4fe1\u53f7\u7eb3\u5165\u672c\u671f\u8fd0\u8425\u590d\u76d8\u3002"
            confidence = "medium"
            statement_type = "inference"
        else:
            judgement = "\u5f53\u524d\u6a21\u5757\u7684\u53ef\u7528\u8bc1\u636e\u6709\u9650\u3002"
            why = "\u6570\u636e\u663e\u793a\u8d44\u6599\u4e0d\u8db3\uff0c\u9700\u8981\u9a8c\u8bc1\u540e\u518d\u5f62\u6210\u660e\u786e\u5224\u65ad\u3002"
            impact = "\u5efa\u8bae\u4f18\u5148\u8865\u5145\u8be5\u6a21\u5757\u6240\u9700\u7684\u89c2\u5bdf\u8d44\u6599\u3002"
            confidence = "low"
            statement_type = "recommendation"
        insights.append({
            "id": f"rule-{module}",
            "module": module,
            "title": f"{module} \u89c2\u5bdf",
            "judgement": judgement,
            "why": why,
            "impact": impact,
            "statement_type": statement_type,
            "evidence_ids": [selected["evidence_id"]],
            "confidence": confidence,
            "scope": {},
            "actions": [{
                "owner": "\u6e20\u9053\u8fd0\u8425",
                "action": "\u590d\u6838\u8bc1\u636e\u5e76\u5b89\u6392\u4e0b\u4e00\u6b65\u9a8c\u8bc1\u3002",
                "deadline": "\u4e0b\u4e00\u5468\u671f",
                "success_metric": "\u4e0b\u4e2a\u5468\u671f\u5b8c\u62101\u6b21\u8bc1\u636e\u590d\u6838\u5e76\u8f93\u51fa1\u6761\u6a21\u5757\u7ed3\u8bba\u3002",
            }],
        })
    return {
        "executive_summary": "\u672c\u62a5\u544a\u57fa\u4e8e\u5df2\u63d0\u4f9b\u8bc1\u636e\u751f\u6210\uff0c\u5efa\u8bae\u5728\u540e\u7eed\u5468\u671f\u7ee7\u7eed\u9a8c\u8bc1\u3002",
        "generation": {"mode": "rule_fallback", "provider": "deterministic_rules"},
        "insights": insights,
    }


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _select_fallback_evidence(rows: list[dict]) -> dict:
    confidence_rank = {"supported": 3, "signal": 2, "validate": 1}

    def score(row: dict) -> tuple[int, int, float, str]:
        scope = row.get("scope") if isinstance(row.get("scope"), dict) else {}
        available = 0 if scope.get("availability") == "insufficient_data" else 1
        confidence = confidence_rank.get(str(row.get("confidence", "supported")), 0)
        sample_size = row.get("sample_size")
        sample = float(sample_size) if isinstance(sample_size, (int, float)) else 0.0
        return (available, confidence, sample, str(row.get("evidence_id", "")))

    return max(rows, key=score)


def _env_secrets(env: Mapping[str, str]) -> set[str]:
    return {
        str(value)
        for key, value in env.items()
        if value and ("KEY" in key.upper() or "TOKEN" in key.upper())
    }


def _strip_secrets(value: Any, secrets: set[str]) -> Any:
    if not secrets:
        return _json_copy(value)
    if isinstance(value, str):
        redacted = value
        for secret in secrets:
            redacted = redacted.replace(secret, "[redacted]")
        return redacted
    if isinstance(value, list):
        return [_strip_secrets(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            _strip_secrets(key, secrets) if isinstance(key, str) else key: _strip_secrets(item, secrets)
            for key, item in value.items()
        }
    return value
