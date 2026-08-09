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
    """Produce concrete, evidence-linked operational insights without a provider."""
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
        if packet.get("role") == "dealer":
            insight = _build_data_grounded_insight(module, rows)
            if statuses.get(module) == "insufficient_data":
                insight["confidence"] = "low"
                insight["statement_type"] = "recommendation"
            insights.append(insight)
        else:
            insights.append(_build_network_fallback_insight(module, rows))
    return {
        "executive_summary": "本报告根据本期经销商经营数据生成，聚焦增长节奏、内容效率、互动转化与区域打法。",
        "generation": {"mode": "rule_fallback", "provider": "data_grounded_rules_v2"},
        "insights": insights,
    }


def _build_network_fallback_insight(module: str, rows: list[dict]) -> dict:
    """Keep Apple-network fallback scoped to its own aggregate evidence schema."""
    selected = _select_fallback_evidence(rows)
    return {
        "id": f"rule-{module}", "module": module, "title": module,
        "judgement": "网络层面已识别出需要优先跟进的经营信号。",
        "why": "该结论基于本期已关联的网络汇总数据。",
        "impact": "建议结合经销商明细，确认信号是否集中在特定区域、账号梯队或内容分类。",
        "statement_type": "inference", "evidence_ids": [selected["evidence_id"]],
        "confidence": "medium", "scope": {},
        "actions": [{"owner": "渠道运营", "action": "在月度复盘中拆解至经销商和城市维度，并确定优先跟进行动。", "deadline": "下一个月度周期", "success_metric": "形成经销商分层的跟进行动清单。"}],
    }


def _build_data_grounded_insight(module: str, rows: list[dict]) -> dict:
    """Turn the curated evidence rows into a useful, auditable operating recommendation."""
    by_suffix = {str(row.get("evidence_id", "")).rsplit(":", 1)[-1]: row for row in rows}
    used: list[dict] = []

    def evidence(suffix: str) -> dict | None:
        row = by_suffix.get(suffix)
        if row is not None:
            used.append(row)
        return row

    def value(row: dict | None) -> float:
        raw = row.get("value") if isinstance(row, dict) else 0
        return float(raw) if isinstance(raw, (int, float)) else 0.0

    def pct(row: dict | None) -> str:
        return f"{value(row) * 100:.1f}%"

    def count(row: dict | None) -> str:
        number = value(row)
        return f"{number:.17g}"

    if module == "growth_diagnosis":
        reads, interactions, fans = (evidence(key) for key in ("q4_reads_completion_rate", "q4_interactions_completion_rate", "q4_fans_completion_rate"))
        judgement = f"增长不是流量不足，而是粉丝沉淀不足：阅读 KPI 已完成 {pct(reads)}，互动完成 {pct(interactions)}，新增粉丝仅完成 {pct(fans)}。"
        why = "内容能把用户带进来并产生互动，但笔记结尾、主页定位和门店咨询入口没有把兴趣稳定转化为关注。"
        impact = "继续单纯加大发布量，会放大阅读与粉丝之间的缺口；下一阶段应把增长目标从曝光转向有效关注。"
        action = "将高互动笔记统一补充关注理由、系列内容预告和门店咨询入口，并单独复盘每类内容的涨粉效率。"
    elif module == "matrix_health":
        concentration, tail = (evidence(key) for key in ("content_homogeneity", "long_tail_note_share"))
        lead = evidence("top_account_read_share")
        if lead:
            account = lead.get("scope", {}).get("account_name", "头部账号")
            judgement = f"矩阵呈现“单账号驱动”特征：{account} 贡献了 {pct(lead)} 的可观测阅读，另有 {pct(tail)} 的笔记处于长尾表现。"
            why = "主账号承担了大部分流量，而门店账号没有形成清晰的本地内容角色，导致账号数量没有转化为稳定的覆盖能力。"
            impact = "一旦头部账号内容失速，整体曝光会明显波动；门店账号需要从转发式供给转为到店服务、城市活动和本地问题解答。"
            action = "保留主账号负责新品与功能内容，门店账号改为本地到店、售后和活动场景，并按城市建立差异化选题清单。"
        else:
            judgement = f"内容集中度指数为 {pct(concentration)}，同时 {pct(tail)} 的笔记处于长尾表现，矩阵尚未形成稳定分工。"
            why = "账号之间的内容角色不清，低效供给没有沉淀为可复用模板。"
            impact = "矩阵规模难以转化为稳定覆盖。"
            action = "明确主账号和门店账号的内容职责，并按月复盘账号贡献。"
    elif module == "content_patterns":
        category_rows = [row for row in rows if str(row.get("evidence_id", "")).endswith("category_reads_per_note")]
        best = max(category_rows, key=value, default=None)
        worst = min(category_rows, key=value, default=None)
        if best is not None:
            used.extend([best, worst] if worst is not None else [best])
            best_name = best.get("scope", {}).get("category", "高效分类")
            worst_name = worst.get("scope", {}).get("category", "低效分类") if worst else "低效分类"
            judgement = f"内容投入产出差异很大：{best_name} 的篇均阅读为 {count(best)}，而 {worst_name} 仅为 {count(worst)}。"
            why = f"{best_name} 更接近用户主动搜索和决策前了解的需求；{worst_name} 的内容形式或利益点没有建立足够的点击理由。"
            impact = "不应平均分配内容资源：高效分类承担破圈，低效分类只有在改版后才值得继续投入。"
            action = f"将 {best_name} 沉淀为标题、封面和讲解结构模板；{worst_name} 暂停扩量，先测试更具体的场景、利益点与首图。"
        else:
            sample = evidence("aggregate_reads_per_note")
            judgement = f"本期内容篇均阅读为 {count(sample)}，但分类明细不足以判断具体选题的优先级。"
            why = "当前可用数据以汇总表现为主，尚不能稳定识别单一分类的优劣。"
            impact = "后续需补充笔记级分类与标题信息，才能提高选题建议的可执行性。"
            action = "下月按统一分类标准标记笔记，并保留标题、封面和发布时间用于复盘。"
    elif module == "user_signals":
        collects, comments, fans, shares = (evidence(key) for key in ("collects_per_read", "comments_per_read", "fans_per_read", "shares_per_read"))
        judgement = f"用户反馈偏“自己留存”而非“主动传播”：收藏率 {pct(collects)} 高于评论率 {pct(comments)}，分享率只有 {pct(shares)}，阅读转粉也仅 {pct(fans)}。"
        why = "现有内容提供了有用信息，却没有把信息价值延伸为关注、转发或门店咨询的下一步动作。"
        impact = "内容会持续产生一次性阅读，但难以沉淀可触达的人群资产，也不利于门店线索转化。"
        action = "在高收藏选题中加入“关注后可持续获得什么”的承诺；为攻略类内容增加可转发清单，为种草类内容增加到店咨询入口。"
    elif module == "regional_strategy":
        city_rows = [row for row in rows if str(row.get("evidence_id", "")).endswith("city_category_efficiency")]
        best = max(city_rows, key=value, default=None)
        worst = min(city_rows, key=value, default=None)
        if best is not None:
            used.extend([best, worst] if worst is not None else [best])
            scope = best.get("scope", {})
            city = scope.get("city", "该城市")
            best_category = scope.get("category", "高效分类")
            worst_category = worst.get("scope", {}).get("category", "低效分类") if worst else "低效分类"
            judgement = f"{city} 不适合“一套内容发所有门店”：{best_category} 的篇均阅读为 {count(best)}，而 {worst_category} 为 {count(worst)}。"
            why = "同一城市中，用户对功能讲解、种草和活动信息的响应不同，说明内容主题比单纯增加门店数量更影响效果。"
            impact = "城市策略应先明确主推内容，再让门店围绕本地活动和服务补充，而不是按相同频率发布同类素材。"
            action = f"{city} 门店以 {best_category} 做内容主线；{worst_category} 仅保留小比例，并以本地活动、到店权益或服务问题重写。"
        else:
            sample = _select_fallback_evidence(rows)
            used.append(sample)
            judgement = "城市维度已具备基础内容表现数据，但缺少可横向比较的多城市样本。"
            why = "当前数据更适合做单城市测试，暂不宜下结论复制到其他区域。"
            impact = "先建立城市化选题台账，后续再比较不同城市的有效打法。"
            action = "为各城市门店统一补充城市标签和内容分类标签。"
    elif module == "action_plan":
        plan = evidence("action_candidate_count")
        judgement = f"当前已形成 {count(plan)} 项可执行动作，重点不在增加更多项目，而在把高效内容复制和低效内容止损排进同一张内容日历。"
        why = "增长、内容与互动信号已经指向同一优先级：先解决粉丝承接，再扩大高效内容供给。"
        impact = "若行动平均铺开，团队会继续花时间在低效分类上，无法改善粉丝增长与矩阵贡献的核心问题。"
        action = "将行动拆为“高效内容复制、低效分类改版、涨粉承接上线”三条工作流，并在月末按阅读、互动、涨粉复盘。"
    else:
        scenarios = [str(row.get("scope", {}).get("scenario", "")) for row in rows if row.get("scope", {}).get("scenario")]
        scenario_names = {"installment_value": "分期价值", "local_service": "本地服务", "student": "学生客群", "trade_in": "以旧换新", "women": "女性客群"}
        readable = "、".join(scenario_names.get(item, item) for item in scenarios[:3]) or "本地需求场景"
        used.extend(rows)
        judgement = f"{readable} 等业务场景尚不能直接被称为“已验证商机”，因为当前内容数据没有把场景、咨询和到店结果连起来。"
        why = "现在能看到内容表现，却看不到用户因哪个场景产生咨询、预约或成交，商业价值仍停留在假设阶段。"
        impact = "若不补齐线索标记，内容团队会把高阅读误判为高商机，无法判断哪些场景值得持续投放。"
        action = "为场景型笔记设置统一关键词和咨询入口，门店记录咨询来源；下个周期用收藏、私信、到店三类信号判断是否扩大测试。"

    evidence_ids = list(dict.fromkeys(row["evidence_id"] for row in used if row.get("evidence_id")))
    if not evidence_ids:
        selected = _select_fallback_evidence(rows)
        evidence_ids = [selected["evidence_id"]]
    return {
        "id": f"rule-{module}", "module": module, "title": module,
        "judgement": judgement, "why": why, "impact": impact,
        "statement_type": "inference", "evidence_ids": evidence_ids,
        "confidence": "medium", "scope": {},
        "actions": [{"owner": "渠道运营", "action": action, "deadline": "下一个月度周期", "success_metric": "形成可复用的内容与运营复盘结论。"}],
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
