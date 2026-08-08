# AI-Generated Xiaohongshu Insight Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing dual-view dashboard into an evidence-backed AI operating insight experience that regenerates from monthly crawler data, historical baselines, and Apple fiscal-quarter KPI progress.

**Architecture:** Keep `build_insight.py` as the single CLI entry and preserve its deterministic KPI logic. Add focused modules for fiscal/history context, evidence generation, AI contract validation, and an OpenAI-compatible provider with cached and rule-based fallbacks; publish role-scoped, versioned JSON that the two static pages render without browser-side model calls.

**Tech Stack:** Python 3.12 standard library, openpyxl, JSON, HTML5, CSS, vanilla JavaScript, Chart.js, Lucide, Python unittest, Node.js test runner.

## Global Constraints

- All time labels and comparisons use Apple fiscal year, fiscal quarter, and fiscal month semantics.
- Python computes and owns all numeric facts; AI explains, prioritizes, and recommends without inventing metrics.
- Every strong AI conclusion references one or more valid `evidence_ids` and distinguishes fact, inference, and action.
- Dealer artifacts and AI prompts contain only the selected dealer's data; Apple artifacts may contain network-level and dealer-level data.
- The browser never receives an API key and never calls the model provider.
- AI mode uses `INSIGHT_AI_API_KEY`, `INSIGHT_AI_BASE_URL`, and `INSIGHT_AI_MODEL`; no new Python package is required.
- Without a key, reuse the latest valid artifact for that month; if none exists, publish a rule-generated fallback with a visible mode label.
- Preserve current data quality publication gates and core-KPI versus expanded-store cohort separation.
- UI uses the supplied large-screen dashboard structure and Apple iOS semantic colors: `#007AFF`, `#34C759`, `#FF9500`, `#FF3B30`, `#AF52DE`, `#F2F2F7`, `#1C1C1E`, `#636366`, and `#D1D1D6`.
- New cards have a maximum `8px` radius; do not use decorative gradients or nested cards.
- This workspace is not currently a Git repository, so task-end commit steps are recorded as verification checkpoints instead of running `git commit`.

---

## File Map

**Create**

- `笔记报告/insight/scripts/fiscal_history.py`: Apple fiscal labels, historical workbook discovery, and historical comparison snapshots.
- `笔记报告/insight/scripts/insight_evidence.py`: deterministic evidence records for all six legacy-report analysis domains.
- `笔记报告/insight/scripts/ai_contract.py`: AI response schema constants, normalization, evidence checks, numeric checks, and role isolation checks.
- `笔记报告/insight/scripts/ai_generation.py`: prompt assembly, OpenAI-compatible HTTP adapter, cache selection, and rule fallback.
- `笔记报告/insight/config/ai_prompt.json`: versioned system instructions and role/module requirements.
- `笔记报告/insight/tests/test_fiscal_history.py`: fiscal and history tests.
- `笔记报告/insight/tests/test_insight_evidence.py`: evidence calculation and legacy-domain coverage tests.
- `笔记报告/insight/tests/test_ai_contract.py`: strict AI output validation tests.
- `笔记报告/insight/tests/test_ai_generation.py`: provider, cache, and fallback tests.
- `笔记报告/insight/tests/test_ai_rendering.mjs`: shared AI card and evidence drawer rendering tests.

**Modify**

- `笔记报告/insight/scripts/build_insight.py`: CLI flags, historical context, AI generation, scoped versioned output, and generation metadata.
- `笔记报告/insight/tests/test_build_insight.py`: end-to-end CLI and scoped artifact assertions.
- `笔记报告/insight/assets/insight-core.js`: schema 2.0 acceptance, AI metadata, shared insight renderer, and evidence lookup.
- `笔记报告/insight/assets/dealer-dashboard.js`: dealer AI view model, filters, and seven analysis modules.
- `笔记报告/insight/assets/apple-dashboard.js`: Apple AI view model, filters, and seven analysis modules.
- `笔记报告/insight/tests/test_insight_core.mjs`: schema 2.0 loading and shared rendering tests.
- `笔记报告/insight/tests/test_dealer_dashboard.mjs`: dealer insight and isolation tests.
- `笔记报告/insight/tests/test_apple_dashboard.mjs`: Apple network insight tests.
- `笔记报告/insight/dealer_insight.html`: AI-first dealer information architecture.
- `笔记报告/insight/apple_insight.html`: AI-first Apple information architecture.
- `笔记报告/insight/assets/insight.css`: large-screen iOS visual system and responsive behavior.
- `笔记报告/insight/index.html`: role entry copy and schema-compatible freshness details.

**Generated During Verification**

- `笔记报告/insight/generated/months/2026-07/apple.json`
- `笔记报告/insight/generated/months/2026-07/dealers/{dealer_id}.json`
- `笔记报告/insight/generated/month_index.json`
- Existing compatibility files under `笔记报告/insight/generated/` remain available until the pages switch fully to the month index.

---

### Task 1: Apple Fiscal Calendar and Historical Comparison Context

**Files:**
- Create: `笔记报告/insight/scripts/fiscal_history.py`
- Create: `笔记报告/insight/tests/test_fiscal_history.py`

**Interfaces:**
- Consumes: source month strings in `YYYY-MM`, the historical data root, and normalized monthly aggregate dictionaries.
- Produces: `apple_period(month: str) -> dict`, `discover_history_workbooks(data_root: Path, through_month: str) -> list[HistoricalSource]`, and `build_history_context(current: dict, history: list[dict]) -> dict`.

- [ ] **Step 1: Write failing fiscal-period tests**

```python
import unittest
from scripts.fiscal_history import apple_period


class ApplePeriodTests(unittest.TestCase):
    def test_october_starts_next_apple_fiscal_year(self):
        self.assertEqual(
            apple_period("2025-10"),
            {"calendar_month": "2025-10", "fiscal_year": "FY26", "fiscal_quarter": "Q1", "fiscal_month": 1},
        )

    def test_july_is_q4_month_one(self):
        period = apple_period("2026-07")
        self.assertEqual((period["fiscal_year"], period["fiscal_quarter"], period["fiscal_month"]), ("FY26", "Q4", 1))
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run: `python -m unittest 笔记报告.insight.tests.test_fiscal_history -v`

Expected: `ModuleNotFoundError` for `scripts.fiscal_history`.

- [ ] **Step 3: Implement the fiscal mapping**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HistoricalSource:
    month: str
    path: Path


def apple_period(month: str) -> dict[str, Any]:
    parsed = datetime.strptime(month, "%Y-%m")
    fiscal_year = parsed.year + 1 if parsed.month >= 10 else parsed.year
    fiscal_month = ((parsed.month - 10) % 12) + 1
    quarter = ((fiscal_month - 1) // 3) + 1
    return {
        "calendar_month": month,
        "fiscal_year": f"FY{str(fiscal_year)[-2:]}",
        "fiscal_quarter": f"Q{quarter}",
        "fiscal_month": fiscal_month - ((quarter - 1) * 3),
    }
```

- [ ] **Step 4: Add failing history ordering and baseline tests**

```python
def test_history_discovery_is_month_sorted_and_stops_before_current(self):
    sources = discover_history_workbooks(self.root, "2026-07")
    self.assertEqual([item.month for item in sources], ["2025-07", "2026-06"])

def test_history_context_returns_previous_yoy_and_rolling_median(self):
    result = build_history_context(
        {"month": "2026-07", "reads": 130, "notes": 10},
        [
            {"month": "2025-07", "reads": 100, "notes": 8},
            {"month": "2026-05", "reads": 90, "notes": 9},
            {"month": "2026-06", "reads": 120, "notes": 10},
        ],
    )
    self.assertEqual(result["previous_month"]["month"], "2026-06")
    self.assertEqual(result["year_ago"]["month"], "2025-07")
    self.assertEqual(result["rolling_baseline"]["reads"], 100)
```

- [ ] **Step 5: Implement deterministic history discovery and comparisons**

Use filename regexes for `总数据YYYY - M`, `总数据YYYY-M`, and Chinese month variants; reject duplicate sources for the same month. `build_history_context` must calculate absolute values and ratios without coercing missing history to zero:

```python
def safe_ratio_change(current: float | None, baseline: float | None) -> float | None:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / baseline


def build_history_context(current: dict, history: list[dict]) -> dict:
    ordered = sorted((row for row in history if row["month"] < current["month"]), key=lambda row: row["month"])
    previous = ordered[-1] if ordered else None
    year_ago_month = f"{int(current['month'][:4]) - 1}{current['month'][4:]}"
    year_ago = next((row for row in ordered if row["month"] == year_ago_month), None)
    window = ordered[-12:]
    return {
        "previous_month": previous,
        "year_ago": year_ago,
        "rolling_baseline": _median_metrics(window, ("reads", "notes", "interactions", "new_fans", "viral_rate")),
        "coverage": {"first_month": ordered[0]["month"] if ordered else None, "months": len(ordered)},
    }
```

- [ ] **Step 6: Run the focused tests**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_fiscal_history.py" -v`

Expected: all fiscal and history tests pass.

- [ ] **Step 7: Record the task checkpoint**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_fiscal_history.py" -v`

Expected: exit code `0`; record the command and test count in the implementation notes.

---

### Task 2: Deterministic Evidence Engine for the Six Legacy Domains

**Files:**
- Create: `笔记报告/insight/scripts/insight_evidence.py`
- Create: `笔记报告/insight/tests/test_insight_evidence.py`

**Interfaces:**
- Consumes: one role-scoped payload, `history_context`, and `apple_period`.
- Produces: `build_evidence_packet(role: str, payload: dict, history_context: dict, period: dict) -> dict` with `evidence`, `module_status`, and `data_scope`.

- [ ] **Step 1: Write a failing evidence-domain coverage test**

```python
from scripts.insight_evidence import build_evidence_packet, REQUIRED_MODULES


def test_packet_covers_every_legacy_analysis_domain():
    packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
    assert set(packet["module_status"]) == set(REQUIRED_MODULES)
    assert {row["module"] for row in packet["evidence"]} == set(REQUIRED_MODULES)
```

Use these exact module keys:

```python
REQUIRED_MODULES = (
    "growth_diagnosis",
    "matrix_health",
    "content_patterns",
    "user_signals",
    "regional_strategy",
    "action_plan",
    "business_opportunities",
)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_insight_evidence.py" -v`

Expected: import failure for `insight_evidence`.

- [ ] **Step 3: Implement the evidence record builder**

```python
def evidence(
    evidence_id: str,
    module: str,
    metric: str,
    value,
    *,
    comparison=None,
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
```

IDs must be stable and role-scoped, for example `dealer:{dealer_id}:2026-07:category:促销:reads_per_note` and `apple:2026-07:region:华东:viral_rate`.

- [ ] **Step 4: Add failing tests for growth, matrix, and content pattern evidence**

```python
def test_growth_evidence_contains_history_and_fiscal_pacing():
    packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
    metrics = {row["metric"] for row in packet["evidence"] if row["module"] == "growth_diagnosis"}
    assert {"reads_change_vs_previous", "reads_change_vs_baseline", "q4_reads_pacing_gap"} <= metrics

def test_content_patterns_separate_viral_long_tail_and_hotspot_notes():
    rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
    pattern_types = {row["scope"].get("pattern_type") for row in rows if row["module"] == "content_patterns"}
    assert {"viral", "long_tail", "hotspot"} <= pattern_types

def test_matrix_health_includes_concentration_and_quadrants():
    rows = build_evidence_packet("apple", apple_fixture(), history_fixture(), period_fixture())["evidence"]
    metrics = {row["metric"] for row in rows if row["module"] == "matrix_health"}
    assert {"top_20_read_share", "quadrant_distribution", "content_homogeneity"} <= metrics
```

- [ ] **Step 5: Implement all evidence families**

Implement focused private functions and concatenate them in `build_evidence_packet`:

```python
def build_evidence_packet(role, payload, history_context, period):
    builders = (
        _growth_evidence,
        _matrix_health_evidence,
        _content_pattern_evidence,
        _user_signal_evidence,
        _regional_strategy_evidence,
        _action_evidence,
        _business_opportunity_evidence,
    )
    rows = []
    for builder in builders:
        rows.extend(builder(role, payload, history_context, period))
    present = {row["module"] for row in rows}
    return {
        "schema_version": "1.0",
        "role": role,
        "period": period,
        "data_scope": _data_scope(payload, history_context),
        "module_status": {module: "ready" if module in present else "insufficient_data" for module in REQUIRED_MODULES},
        "evidence": rows,
    }
```

Evidence logic must include:

- Growth: current, previous, year-ago, rolling baseline, quarter-to-date KPI pacing, reads/interaction/fans divergence.
- Matrix: account/dealer quadrants, S/A/B/C tier candidates, top-20 share, long-tail share, posting frequency, category-share similarity.
- Content: Top 20 notes, viral threshold and rate, long-tail age, hotspot recency, title tokens, format and category performance.
- User signals: like/save/comment/share structure, fan-to-read ratio, high-save and high-comment notes, anomaly candidates.
- Region: city/account/category efficiency, sample size, confidence, and test-only recommendations for sparse cities.
- Action: deterministic candidate actions for 30, 60, and 90 days with measurable outcomes.
- Opportunity: demand, competition concentration, supply gap, and re-validation of trade-in, local service, installment/value, women, and student scenarios.

- [ ] **Step 6: Add and pass role-isolation and sparse-data tests**

```python
def test_dealer_packet_never_contains_peer_identity():
    packet = build_evidence_packet("dealer", dealer_fixture(), history_fixture(), period_fixture())
    serialized = json.dumps(packet, ensure_ascii=False)
    assert "PEER_DEALER_NAME" not in serialized

def test_sparse_city_is_validate_confidence_not_supported():
    packet = build_evidence_packet("dealer", sparse_city_fixture(), history_fixture(), period_fixture())
    city_rows = [row for row in packet["evidence"] if row["module"] == "regional_strategy"]
    assert all(row["confidence"] == "validate" for row in city_rows)
```

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_insight_evidence.py" -v`

Expected: all evidence tests pass and no non-finite number is serializable.

- [ ] **Step 7: Record the task checkpoint**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_insight_evidence.py" -v`

Expected: exit code `0`; retain the fixture output for Task 3.

---

### Task 3: Strict AI Insight Contract and Validators

**Files:**
- Create: `笔记报告/insight/scripts/ai_contract.py`
- Create: `笔记报告/insight/tests/test_ai_contract.py`

**Interfaces:**
- Consumes: raw AI JSON, an evidence packet, and `allowed_entity_ids`.
- Produces: `validate_ai_result(result: dict, packet: dict, allowed_entity_ids: set[str]) -> dict`; raises `AIContractError` with machine-readable `errors`.

- [ ] **Step 1: Write failing valid-contract and missing-evidence tests**

```python
from scripts.ai_contract import AIContractError, validate_ai_result


def test_valid_result_preserves_evidence_links(self):
    result = validate_ai_result(valid_ai_result(), evidence_packet(), {"dealer-1", "account-1"})
    self.assertEqual(result["insights"][0]["evidence_ids"], ["ev-1"])

def test_unknown_evidence_id_is_rejected(self):
    value = valid_ai_result()
    value["insights"][0]["evidence_ids"] = ["made-up"]
    with self.assertRaisesRegex(AIContractError, "unknown_evidence"):
        validate_ai_result(value, evidence_packet(), {"dealer-1"})
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_contract.py" -v`

Expected: import failure for `ai_contract`.

- [ ] **Step 3: Define the exact normalized contract**

```python
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_STATEMENT_TYPES = {"fact", "inference", "recommendation"}
REQUIRED_MODULES = {
    "growth_diagnosis", "matrix_health", "content_patterns", "user_signals",
    "regional_strategy", "action_plan", "business_opportunities",
}


class AIContractError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))
```

The top-level result must contain `executive_summary`, `insights`, and `generation`. Every insight must contain `id`, `module`, `title`, `judgement`, `why`, `impact`, `statement_type`, `evidence_ids`, `confidence`, `scope`, and `actions`. Every action must contain `owner`, `action`, `deadline`, and `success_metric`.

- [ ] **Step 4: Implement structural, evidence, numeric, and entity validation**

```python
def validate_ai_result(result, packet, allowed_entity_ids):
    errors = []
    evidence_by_id = {row["evidence_id"]: row for row in packet["evidence"]}
    _validate_top_level(result, errors)
    for item in result.get("insights", []):
        _validate_insight_shape(item, errors)
        _validate_evidence_links(item, evidence_by_id, errors)
        _validate_numbers(item, evidence_by_id, errors)
        _validate_entities(item, allowed_entity_ids, errors)
    _validate_module_coverage(result, packet["module_status"], errors)
    if errors:
        raise AIContractError(errors)
    return _normalize_result(result)
```

Numeric validation extracts Arabic numbers and percentages from `judgement`, `why`, and `impact`; each must equal a numeric value in linked evidence after accepted percent formatting. Chinese words such as “三类” are treated as prose, not numeric facts.

- [ ] **Step 5: Add failing privacy, fabricated-number, and incomplete-action tests**

```python
def test_unknown_entity_is_rejected(self):
    value = valid_ai_result()
    value["insights"][0]["scope"]["entity_ids"] = ["peer-dealer"]
    with self.assertRaisesRegex(AIContractError, "unknown_entity"):
        validate_ai_result(value, evidence_packet(), {"dealer-1"})

def test_unlinked_numeric_claim_is_rejected(self):
    value = valid_ai_result()
    value["insights"][0]["judgement"] = "阅读量增长了99%。"
    with self.assertRaisesRegex(AIContractError, "unsupported_number"):
        validate_ai_result(value, evidence_packet(), {"dealer-1"})

def test_action_requires_owner_deadline_and_metric(self):
    value = valid_ai_result()
    value["insights"][0]["actions"] = [{"action": "增加场景内容"}]
    with self.assertRaisesRegex(AIContractError, "incomplete_action"):
        validate_ai_result(value, evidence_packet(), {"dealer-1"})
```

- [ ] **Step 6: Run the complete contract test file**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_contract.py" -v`

Expected: all valid and invalid contract cases pass.

- [ ] **Step 7: Record the task checkpoint**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_contract.py" -v`

Expected: exit code `0` and deterministic error codes.

---

### Task 4: Prompt, Provider Adapter, Cache, and Rule Fallback

**Files:**
- Create: `笔记报告/insight/config/ai_prompt.json`
- Create: `笔记报告/insight/scripts/ai_generation.py`
- Create: `笔记报告/insight/tests/test_ai_generation.py`

**Interfaces:**
- Consumes: evidence packet, role, output cache path, environment mapping, and injectable HTTP transport.
- Produces: `generate_ai_insights(packet, *, cache_path: Path, env: Mapping[str, str], transport=None) -> dict` with `generation.mode` equal to `ai`, `cached_ai`, or `rule_fallback`.

- [ ] **Step 1: Create the versioned prompt configuration**

```json
{
  "prompt_version": "2026-08-08.1",
  "system": "You are a channel operations analyst. Use only the supplied evidence. Return JSON only. Do not calculate new metrics. Separate facts, inferences, and recommendations. Every strong conclusion must cite evidence_ids.",
  "roles": {
    "dealer": "Analyze only this dealer. Never compare with or name another dealer.",
    "apple": "Analyze the network, dealer tiers, regional differences, reusable patterns, risks, and resource allocation."
  },
  "required_modules": [
    "growth_diagnosis",
    "matrix_health",
    "content_patterns",
    "user_signals",
    "regional_strategy",
    "action_plan",
    "business_opportunities"
  ]
}
```

- [ ] **Step 2: Write failing tests for the three generation modes**

```python
def test_key_uses_provider_and_returns_ai_mode(tmp_path):
    result = generate_ai_insights(packet(), cache_path=tmp_path / "ai.json", env=ai_env(), transport=fake_transport)
    assert result["generation"]["mode"] == "ai"

def test_no_key_uses_valid_same_month_cache(tmp_path):
    cache = write_cache(tmp_path, valid_result(mode="ai"))
    result = generate_ai_insights(packet(), cache_path=cache, env={})
    assert result["generation"]["mode"] == "cached_ai"

def test_no_key_and_no_cache_uses_rule_fallback(tmp_path):
    result = generate_ai_insights(packet(), cache_path=tmp_path / "missing.json", env={})
    assert result["generation"]["mode"] == "rule_fallback"
    assert {item["module"] for item in result["insights"]} == set(REQUIRED_MODULES)
```

- [ ] **Step 3: Run the tests and verify failure**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_generation.py" -v`

Expected: import failure for `ai_generation`.

- [ ] **Step 4: Implement the OpenAI-compatible request adapter with standard library HTTP**

```python
def _provider_request(packet, prompt, env, transport):
    base_url = env.get("INSIGHT_AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": env["INSIGHT_AI_MODEL"],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "system", "content": prompt["roles"][packet["role"]]},
            {"role": "user", "content": json.dumps(packet, ensure_ascii=False, allow_nan=False)},
        ],
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {env['INSIGHT_AI_API_KEY']}", "Content-Type": "application/json"},
        method="POST",
    )
    response = (transport or urllib.request.urlopen)(request, timeout=90)
    payload = json.loads(response.read().decode("utf-8"))
    return json.loads(payload["choices"][0]["message"]["content"])
```

- [ ] **Step 5: Implement cache validation and deterministic fallback**

```python
def generate_ai_insights(packet, *, cache_path, env, transport=None):
    allowed_ids = set(packet["data_scope"].get("allowed_entity_ids", []))
    if env.get("INSIGHT_AI_API_KEY") and env.get("INSIGHT_AI_MODEL"):
        raw = _provider_request(packet, load_prompt(), env, transport)
        result = validate_ai_result(raw, packet, allowed_ids)
        result["generation"].update({"mode": "ai", "model": env["INSIGHT_AI_MODEL"]})
        _write_cache(cache_path, result)
        return result
    cached = _read_valid_same_period_cache(cache_path, packet, allowed_ids)
    if cached:
        cached["generation"]["mode"] = "cached_ai"
        return cached
    return validate_ai_result(build_rule_fallback(packet), packet, allowed_ids)
```

`build_rule_fallback` must select the highest-priority evidence per ready module, use non-causal wording such as “数据显示” and “建议验证”, and create one measurable action per module.

- [ ] **Step 6: Add provider failure and invalid cache tests**

```python
def test_provider_contract_failure_falls_back_to_valid_cache(tmp_path):
    cache = write_cache(tmp_path, valid_result(mode="ai"))
    result = generate_ai_insights(packet(), cache_path=cache, env=ai_env(), transport=invalid_transport)
    assert result["generation"]["mode"] == "cached_ai"

def test_cache_from_another_month_is_not_reused(tmp_path):
    cache = write_cache(tmp_path, valid_result(period="2026-06"))
    result = generate_ai_insights(packet(period="2026-07"), cache_path=cache, env={})
    assert result["generation"]["mode"] == "rule_fallback"
```

- [ ] **Step 7: Run generation tests**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_generation.py" -v`

Expected: provider, cache, and fallback tests all pass without network access.

- [ ] **Step 8: Record the task checkpoint**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_ai_*.py" -v`

Expected: Tasks 3 and 4 tests pass together.

---

### Task 5: Integrate History, Evidence, and AI into the Monthly Builder

**Files:**
- Modify: `笔记报告/insight/scripts/build_insight.py`
- Modify: `笔记报告/insight/tests/test_build_insight.py`

**Interfaces:**
- Consumes: Tasks 1-4 public functions.
- Produces: schema `2.0` payloads, versioned monthly paths, role-scoped evidence, and compatibility files.

- [ ] **Step 1: Add failing CLI argument tests**

```python
def test_cli_accepts_ai_and_versioned_month_output(self):
    result = build_insight.main([
        "--month", "2026-07",
        "--data-root", str(self.data_root),
        "--output-dir", str(self.output_dir),
        "--ai",
    ])
    self.assertEqual(result, 0)
    self.assertTrue((self.output_dir / "month_index.json").exists())
    self.assertTrue((self.output_dir / "months" / "2026-07" / "apple.json").exists())
```

- [ ] **Step 2: Run the new CLI test and verify failure**

Run: `python -m unittest 笔记报告.insight.tests.test_build_insight.MonthlySourceTests.test_cli_accepts_ai_and_versioned_month_output -v`

Expected: argument parser rejects `--ai` or the versioned file is missing.

- [ ] **Step 3: Add CLI flags and orchestration**

Add:

```python
parser.add_argument("--ai", action="store_true", help="Generate validated AI insights or use a validated fallback.")
parser.add_argument("--no-compat", action="store_true", help="Do not update legacy latest-path JSON files.")
```

After `build_insight_payload`, create history context, evidence packets, and AI output. `--ai` enables provider calls; when omitted, pass an empty environment to force cache/fallback behavior so every published payload still contains an `ai_insights` contract.

- [ ] **Step 4: Upgrade the payload contract without changing deterministic metric fields**

```python
payload["schema_version"] = "2.0"
payload["period"] = apple_period(month)
payload["history"] = history_context
payload["metadata"]["logic_version"] = "2026-08-08.1"
payload["metadata"]["prompt_version"] = prompt_config["prompt_version"]
payload["apple"]["evidence"] = apple_packet["evidence"]
payload["apple"]["ai_insights"] = apple_ai
```

For each dealer, attach only its own `evidence` and `ai_insights` before writing the scoped file. Do not attach all dealer AI packets to `insight_data.json`.

- [ ] **Step 5: Implement versioned artifact writers and index**

```python
def write_versioned_artifacts(output_dir, payload, dealer_results):
    month = payload["source_month"]
    month_dir = output_dir / "months" / month
    _write_json(month_dir / "apple.json", build_apple_month_payload(payload))
    for dealer_id, dealer_payload in dealer_results.items():
        _write_json(month_dir / "dealers" / f"{dealer_id}.json", dealer_payload)
    index = load_month_index(output_dir / "month_index.json")
    index["schema_version"] = "2.0"
    index["latest_month"] = max(set(index.get("months", [])) | {month})
    index["months"] = sorted(set(index.get("months", [])) | {month})
    _write_json(output_dir / "month_index.json", index)
```

- [ ] **Step 6: Add scoped privacy and compatibility tests**

```python
def test_versioned_dealer_artifact_contains_no_peer_identity(self):
    artifact = json.loads(self.dealer_path.read_text(encoding="utf-8"))
    serialized = json.dumps(artifact, ensure_ascii=False)
    self.assertIn("SELECTED_DEALER", serialized)
    self.assertNotIn("PEER_DEALER", serialized)

def test_latest_compatibility_files_are_written_by_default(self):
    self.assertTrue((self.output_dir / "insight_data.json").exists())
    self.assertTrue((self.output_dir / "dealer_index.json").exists())
```

- [ ] **Step 7: Run all Python tests**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_*.py" -v`

Expected: existing and new tests pass; the old 1.0 metrics remain unchanged except for the schema version and added fields.

- [ ] **Step 8: Record the task checkpoint**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_*.py" -v`

Expected: exit code `0`; record the total Python test count.

---

### Task 6: Shared Frontend AI Rendering and Month Loading

**Files:**
- Modify: `笔记报告/insight/assets/insight-core.js`
- Create: `笔记报告/insight/tests/test_ai_rendering.mjs`
- Modify: `笔记报告/insight/tests/test_insight_core.mjs`

**Interfaces:**
- Consumes: schema 2.0 monthly payloads from Task 5.
- Produces: `loadMonthIndex`, `renderInsightCard`, `renderExecutiveBrief`, `renderEvidenceList`, `groupInsightsByModule`, and AI generation labels on `global.InsightCore`.

- [ ] **Step 1: Write failing schema and grouping tests**

```javascript
test("loadData accepts schema 2.0 monthly payloads", async () => {
  const core = await loadCore({ fetch: async () => okJson(makePayload({ schema_version: "2.0" })) });
  assert.equal((await core.loadData("month.json")).schema_version, "2.0");
});

test("groupInsightsByModule preserves generator order", async () => {
  const core = await loadCore();
  const grouped = core.groupInsightsByModule([
    { id: "a", module: "growth_diagnosis" },
    { id: "b", module: "content_patterns" },
    { id: "c", module: "growth_diagnosis" },
  ]);
  assert.deepEqual(grouped.growth_diagnosis.map((item) => item.id), ["a", "c"]);
});
```

- [ ] **Step 2: Run tests and verify the new cases fail**

Run: `node --test 笔记报告/insight/tests/test_insight_core.mjs 笔记报告/insight/tests/test_ai_rendering.mjs`

Expected: missing functions or unsupported schema failure.

- [ ] **Step 3: Implement schema compatibility and month index loading**

```javascript
const SUPPORTED_SCHEMAS = new Set(["1.0", "2.0"]);

async function loadMonthIndex(url = "generated/month_index.json") {
  const index = await fetchJson(url);
  if (!index || index.schema_version !== "2.0" || !Array.isArray(index.months)) {
    throw new Error("月份索引无效，请重新生成 Insight 数据。");
  }
  return index;
}
```

Keep the existing `loadData` quality checks and add period/generation shape checks only for schema 2.0.

- [ ] **Step 4: Implement escaped AI card and evidence rendering**

```javascript
function renderInsightCard(item, evidenceById) {
  const evidence = asArray(item.evidence_ids).map((id) => evidenceById[id]).filter(Boolean);
  return `<article class="ai-insight ai-insight--${escapeHtml(item.confidence || "low")}">
    <header class="ai-insight__header">
      <span class="ai-insight__type">${escapeHtml(statementTypeLabel(item.statement_type))}</span>
      <span class="ai-insight__confidence">${escapeHtml(confidenceLabel(item.confidence))}</span>
    </header>
    <h3>${escapeHtml(item.title)}</h3>
    <p class="ai-insight__judgement">${escapeHtml(item.judgement)}</p>
    <p>${escapeHtml(item.why)}</p>
    ${renderActions(item.actions)}
    <details class="ai-evidence"><summary>查看数据依据</summary>${renderEvidenceList(evidence)}</details>
  </article>`;
}
```

- [ ] **Step 5: Add XSS, missing-evidence, and generation-mode tests**

```javascript
test("renderInsightCard escapes model supplied text", async () => {
  const html = core.renderInsightCard({ ...insight(), title: "<img src=x onerror=alert(1)>" }, evidenceMap());
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&lt;img/);
});

test("rule fallback is visibly labeled", async () => {
  assert.equal(core.generationModeLabel("rule_fallback"), "规则降级分析");
});
```

- [ ] **Step 6: Run shared frontend tests**

Run: `node --test 笔记报告/insight/tests/test_insight_core.mjs 笔记报告/insight/tests/test_ai_rendering.mjs`

Expected: all shared rendering and legacy core tests pass.

- [ ] **Step 7: Record the task checkpoint**

Run: `node --test 笔记报告/insight/tests/test_insight_core.mjs 笔记报告/insight/tests/test_ai_rendering.mjs`

Expected: exit code `0`; record the Node test count.

---

### Task 7: Dealer AI-First Page and Scoped Monthly Navigation

**Files:**
- Modify: `笔记报告/insight/dealer_insight.html`
- Modify: `笔记报告/insight/assets/dealer-dashboard.js`
- Modify: `笔记报告/insight/tests/test_dealer_dashboard.mjs`

**Interfaces:**
- Consumes: `generated/month_index.json`, `generated/dealer_index.json`, and `generated/months/{month}/dealers/{dealer_id}.json`.
- Produces: dealer executive brief plus seven module sections, filtered to selected dealer/city/account/category/format.

- [ ] **Step 1: Write failing monthly loading and privacy tests**

```javascript
test("dealer page loads only the selected month and dealer artifact", async () => {
  await runScopedDashboard({ href: "?dealer_id=dealer-1&month=2026-07", loadData });
  assert.deepEqual(requestedUrls, [
    "generated/month_index.json",
    "generated/dealer_index.json",
    "generated/months/2026-07/dealers/dealer-1.json",
  ]);
  assert.ok(requestedUrls.every((url) => !url.endsWith("apple.json")));
});

test("dealer AI view contains no peer insight", async () => {
  const model = dashboard.buildDealerAIViewModel(scopedDealerPayload(), filters());
  assert.doesNotMatch(JSON.stringify(model), /PEER_DEALER/);
});
```

- [ ] **Step 2: Run dealer tests and verify failure**

Run: `node --test 笔记报告/insight/tests/test_dealer_dashboard.mjs`

Expected: monthly route or AI view model assertions fail.

- [ ] **Step 3: Replace the main dealer HTML hierarchy with AI-first sections**

Keep the sidebar and toolbar, add a month select, and use these exact section IDs in order:

```html
<section id="ai-brief" class="dashboard-section ai-brief-section" aria-labelledby="ai-brief-title">
  <header class="section-heading"><h1 id="ai-brief-title">本月经营判断</h1><span id="ai-mode-badge"></span></header>
  <div id="executive-brief"></div>
</section>
<section id="growth-diagnosis" class="dashboard-section insight-module"></section>
<section id="matrix-health" class="dashboard-section insight-module"></section>
<section id="content-patterns" class="dashboard-section insight-module"></section>
<section id="user-signals" class="dashboard-section insight-module"></section>
<section id="regional-strategy" class="dashboard-section insight-module"></section>
<section id="action-plan" class="dashboard-section insight-module"></section>
<section id="business-opportunities" class="dashboard-section insight-module"></section>
```

Move existing KPI, category, format, account, and action widgets into evidence containers under their matching module; do not delete their accessible empty and chart fallback states.

- [ ] **Step 4: Implement dealer AI view-model filtering**

```javascript
function buildDealerAIViewModel(payload, filters) {
  const dealer = payload.dealer || selectDealer(payload.dealers, filters.dealerId);
  const evidence = filterDealerEvidence(asArray(dealer.evidence), filters);
  const allowedEvidence = new Set(evidence.map((row) => row.evidence_id));
  const insights = asArray(dealer.ai_insights && dealer.ai_insights.insights).filter(function (item) {
    return insightMatchesFilters(item, filters) && asArray(item.evidence_ids).some((id) => allowedEvidence.has(id));
  });
  return {
    executiveSummary: dealer.ai_insights.executive_summary,
    modules: InsightCore.groupInsightsByModule(insights),
    evidenceById: Object.fromEntries(evidence.map((row) => [row.evidence_id, row])),
    generation: dealer.ai_insights.generation,
  };
}
```

Dealer-wide insights remain visible when city/account/category filters are empty; targeted insights appear only when their scope matches the selected values.

- [ ] **Step 5: Add module coverage and sparse-city tests**

```javascript
test("dealer renders all seven legacy analysis modules", async () => {
  await runDashboardPage(scopedDealerPayload());
  for (const id of REQUIRED_MODULE_IDS) assert.ok(document.getElementById(id));
});

test("sparse city recommendation is labeled as validation", async () => {
  await runDashboardPage(sparseCityPayload());
  assert.match(document.getElementById("regional-strategy").innerHTML, /待验证/);
});
```

- [ ] **Step 6: Run dealer tests**

Run: `node --test 笔记报告/insight/tests/test_dealer_dashboard.mjs`

Expected: all old scoped-loading tests and new AI module tests pass.

- [ ] **Step 7: Record the task checkpoint**

Run: `node --test 笔记报告/insight/tests/test_dealer_dashboard.mjs`

Expected: exit code `0`; inspect the serialized test DOM to confirm no peer name.

---

### Task 8: Apple Network AI-First Page

**Files:**
- Modify: `笔记报告/insight/apple_insight.html`
- Modify: `笔记报告/insight/assets/apple-dashboard.js`
- Modify: `笔记报告/insight/tests/test_apple_dashboard.mjs`

**Interfaces:**
- Consumes: `generated/month_index.json` and `generated/months/<month>/apple.json`.
- Produces: Apple executive brief, network/dealer-tier analysis, regional opportunity map, reusable cases, risks, and resource actions.

- [ ] **Step 1: Write failing monthly loading and network-module tests**

```javascript
test("Apple page loads selected monthly network artifact", async () => {
  await runDashboardPage(monthIndexThenApplePayload(), { href: "?month=2026-07" });
  assert.deepEqual(requestedUrls, ["generated/month_index.json", "generated/months/2026-07/apple.json"]);
});

test("Apple view model preserves dealer tier and resource allocation insights", async () => {
  const model = dashboard.buildAppleAIViewModel(makeApplePayload(), filters());
  assert.ok(model.modules.matrix_health.some((item) => item.scope.tier === "A"));
  assert.ok(model.modules.action_plan.some((item) => item.scope.action_type === "resource_allocation"));
});
```

- [ ] **Step 2: Run Apple tests and verify failure**

Run: `node --test 笔记报告/insight/tests/test_apple_dashboard.mjs`

Expected: monthly loading and AI model assertions fail.

- [ ] **Step 3: Replace the Apple main hierarchy with the same seven module IDs**

Use the same module IDs as the dealer page so shared navigation and CSS work. Apple-specific evidence panels under those modules must include:

- Growth: network KPI pacing and historical attribution.
- Matrix health: S/A/B/C distribution, quadrants, concentration, and risk table.
- Content patterns: Top 20, long-tail, hotspot, title patterns, and replicable cases.
- User signals: interaction structure, fan/read divergence, and mindshare inference.
- Regional strategy: region/city/category opportunity tables.
- Action plan: Apple events, dealer coaching, and resource allocation.
- Business opportunities: demand/competition/supply-gap validation.

- [ ] **Step 4: Implement composable Apple AI filters**

```javascript
function buildAppleAIViewModel(payload, filters) {
  const apple = payload.apple;
  const evidence = filterAppleEvidence(asArray(apple.evidence), filters);
  const evidenceIds = new Set(evidence.map((row) => row.evidence_id));
  const insights = asArray(apple.ai_insights && apple.ai_insights.insights).filter(function (item) {
    return appleInsightMatchesFilters(item, filters)
      && asArray(item.evidence_ids).some((id) => evidenceIds.has(id));
  });
  return {
    executiveSummary: apple.ai_insights.executive_summary,
    modules: InsightCore.groupInsightsByModule(insights),
    evidenceById: Object.fromEntries(evidence.map((row) => [row.evidence_id, row])),
    generation: apple.ai_insights.generation,
  };
}
```

Network-wide insights remain visible under filters only when their scope explicitly declares `network_wide: true`; filtered sections never substitute unrelated network totals for missing city/category evidence.

- [ ] **Step 5: Add complete module, inference-label, and empty-state tests**

```javascript
test("Apple renders all legacy domains and marks mindshare as inference", async () => {
  await runDashboardPage(makeApplePayload());
  for (const id of REQUIRED_MODULE_IDS) assert.ok(document.getElementById(id));
  assert.match(document.getElementById("user-signals").innerHTML, /AI 推断/);
});

test("filtered module with no matching evidence shows a bounded empty state", async () => {
  const html = dashboard.renderInsightModule("content_patterns", [], {});
  assert.match(html, /当前筛选范围暂无可支持的洞察/);
});
```

- [ ] **Step 6: Run Apple tests**

Run: `node --test 笔记报告/insight/tests/test_apple_dashboard.mjs`

Expected: all old network reconciliation tests and new AI tests pass.

- [ ] **Step 7: Record the task checkpoint**

Run: `node --test 笔记报告/insight/tests/test_apple_dashboard.mjs`

Expected: exit code `0`; record the test count.

---

### Task 9: Large-Screen Apple iOS Visual System and Responsive Layout

**Files:**
- Modify: `笔记报告/insight/assets/insight.css`
- Modify: `笔记报告/insight/index.html`
- Modify: `笔记报告/insight/tests/test_insight_core.mjs`

**Interfaces:**
- Consumes: HTML structures from Tasks 7-8.
- Produces: consistent iOS semantic styling across role entry, Apple, and dealer pages.

- [ ] **Step 1: Add static visual-contract tests**

```javascript
test("stylesheet defines required iOS semantic tokens", () => {
  const css = readFileSync(new URL("../assets/insight.css", import.meta.url), "utf8");
  for (const color of ["#007AFF", "#34C759", "#FF9500", "#FF3B30", "#AF52DE", "#F2F2F7"]) {
    assert.match(css.toUpperCase(), new RegExp(color.toUpperCase()));
  }
  assert.doesNotMatch(css, /border-radius:\s*(?:[1-9]\d|9)px/);
});
```

- [ ] **Step 2: Run the visual contract test and verify failure**

Run: `node --test 笔记报告/insight/tests/test_insight_core.mjs`

Expected: one or more required tokens or radius constraints fail.

- [ ] **Step 3: Replace global tokens and semantic component colors**

```css
:root {
  --ios-blue: #007AFF;
  --ios-green: #34C759;
  --ios-orange: #FF9500;
  --ios-red: #FF3B30;
  --ios-purple: #AF52DE;
  --ios-background: #F2F2F7;
  --ios-surface: #FFFFFF;
  --ios-label: #1C1C1E;
  --ios-secondary-label: #636366;
  --ios-separator: #D1D1D6;
  --panel-radius: 8px;
}
```

Map opportunity, attention, risk, and AI inference states to green, orange, red, and purple. Blue is reserved for selection, primary trend, and interaction affordances.

- [ ] **Step 4: Implement stable large-screen layout**

```css
.app-shell { display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 100vh; }
.main-canvas { width: min(100%, 1600px); margin: 0 auto; padding: 20px 24px 48px; }
.ai-brief-grid { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.8fr); gap: 16px; }
.insight-evidence-layout { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr); gap: 16px; }
.ai-insight, .panel, .chart-panel, .table-panel { border-radius: var(--panel-radius); }
```

- [ ] **Step 5: Add responsive rules with no viewport-scaled type**

```css
@media (max-width: 900px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { position: static; width: auto; }
  .sidebar__nav { display: flex; overflow-x: auto; }
  .ai-brief-grid, .insight-evidence-layout, .panel-grid { grid-template-columns: 1fr; }
  .top-toolbar { align-items: flex-start; flex-wrap: wrap; }
}
```

Use fixed/rem font sizes, `min-width: 0`, `overflow-wrap: anywhere`, and explicit chart aspect ratios. Do not add `vw` font sizes, gradients, decorative blobs, or rounded pills for commands that have a Lucide icon.

- [ ] **Step 6: Update the role entry page**

Keep the first screen as a role entry, not a marketing landing page. Show Apple and dealer destinations as two compact access choices, with current source month and analysis mode; use the same background, surface, semantic colors, and 8px radius.

- [ ] **Step 7: Run static frontend tests**

Run: `node --test 笔记报告/insight/tests/test_*.mjs`

Expected: all frontend tests pass, including visual token checks.

- [ ] **Step 8: Record the task checkpoint**

Run: `node --test 笔记报告/insight/tests/test_*.mjs`

Expected: exit code `0`; record the Node test count.

---

### Task 10: Generate the July Demonstration, Full Regression, and Browser Verification

**Files:**
- Generate: `笔记报告/insight/generated/months/2026-07/apple.json`
- Generate: `笔记报告/insight/generated/months/2026-07/dealers/*.json`
- Generate: `笔记报告/insight/generated/month_index.json`
- Modify only if verification finds defects: files owned by Tasks 1-9 and their corresponding tests.

**Interfaces:**
- Consumes: the complete implementation and real data under `数据/`.
- Produces: a reproducible July demo and verified local URLs.

- [ ] **Step 1: Run the complete automated test suite before generation**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_*.py" -v`

Expected: all Python tests pass.

Run: `node --test 笔记报告/insight/tests/test_*.mjs`

Expected: all frontend tests pass.

- [ ] **Step 2: Generate July artifacts without requiring a live key**

Run: `python 笔记报告/insight/scripts/build_insight.py --month 2026-07 --ai`

Expected: exit code `0`; quality status is `ready` or `ready_with_warnings`; Apple and every publishable dealer receive an AI, cached-AI, or rule-fallback result; `month_index.json` lists `2026-07`.

- [ ] **Step 3: Validate generated contracts and privacy from disk**

Run:

```powershell
python -m json.tool 笔记报告/insight/generated/months/2026-07/apple.json > $null
Get-ChildItem 笔记报告/insight/generated/months/2026-07/dealers/*.json | ForEach-Object { python -m json.tool $_.FullName > $null }
```

Expected: every JSON file parses successfully. Run the Python role-isolation validator over all dealer files and expect zero peer-identity violations and zero unknown evidence references.

- [ ] **Step 4: Start or reuse the local static server**

Run: `python -m http.server 8000 --bind 127.0.0.1`

Expected: server remains available at `http://127.0.0.1:8000/`. If port 8000 is occupied by this project, reuse it; if occupied by another process, use 8001.

- [ ] **Step 5: Verify both pages in a real browser at desktop and mobile sizes**

Open:

- `http://127.0.0.1:8000/笔记报告/insight/apple_insight.html?month=2026-07`
- `http://127.0.0.1:8000/笔记报告/insight/dealer_insight.html?month=2026-07&dealer_id=dealer-00033433d147`

Capture screenshots at `1440x1000`, `1024x768`, and `390x844`. Confirm:

- The first viewport leads with AI judgement and priority actions.
- All seven analysis modules exist and contain either insights or explicit insufficient-data states.
- Evidence drawers open and show only linked evidence.
- Apple filters compose correctly; dealer filters never introduce peer data.
- Month switching changes the JSON route and visible Apple fiscal labels.
- Chart.js unavailable and constructor-failure paths still leave textual evidence visible.
- No text overflow, overlap, blank chart area without fallback, horizontal page scroll, or clipped controls.

- [ ] **Step 6: Check browser console and canvas pixels**

Expected: no uncaught JavaScript errors, failed local JSON requests, or invalid ARIA references. For every visible canvas, verify a non-background pixel sample exists; otherwise the textual fallback must be visible.

- [ ] **Step 7: Re-run all tests after browser fixes**

Run: `python -m unittest discover -s 笔记报告/insight/tests -p "test_*.py" -v`

Run: `node --test 笔记报告/insight/tests/test_*.mjs`

Expected: both suites exit `0`.

- [ ] **Step 8: Record the final verification checkpoint**

Record the final Python and Node test counts, generated analysis mode, data quality warnings, screenshot paths, and working local URLs. Do not claim live-AI success unless the provider was actually called and the returned artifact has `generation.mode: "ai"`.

---

## Plan Self-Review

- **Spec coverage:** Tasks 1-5 implement Apple fiscal history, monthly refresh, deterministic facts, all six legacy report areas plus the required regional module, role isolation, AI generation, validation, cache, fallback, and versioning. Tasks 6-9 implement AI-first presentation, both roles, iOS styling, filtering, evidence display, and responsive behavior. Task 10 covers data generation and end-to-end acceptance.
- **Legacy report mapping:** `growth_diagnosis`, `matrix_health`, `content_patterns`, `user_signals`, `action_plan`, and `business_opportunities` directly cover the old report; `regional_strategy` implements the added city/region requirement.
- **Type consistency:** `build_evidence_packet` feeds `generate_ai_insights`; `validate_ai_result` consumes the same evidence packet; backend `module` and `evidence_id` names match `groupInsightsByModule`, `buildDealerAIViewModel`, and `buildAppleAIViewModel` in the frontend.
- **Privacy boundary:** Dealer evidence is scoped before prompting and before file publication, rather than filtered from a shared browser payload.
- **Fallback boundary:** A missing key never blocks monthly generation, while cached output is reused only for the exact role/entity/month and only after current validation.
- **Placeholder scan:** The plan contains no deferred implementation markers; brace-delimited route segments are runtime contract notation.
