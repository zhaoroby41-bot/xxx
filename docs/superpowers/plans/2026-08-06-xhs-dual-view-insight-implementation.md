# 小红书运营 Insight 双视角 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有硬编码小红书报告升级为共享数据模型驱动的经销商与 Apple 双视角运营看板。

**Architecture:** 使用 Python 读取和标准化 Excel，生成一个版本化 `insight_data.json`；两个静态 HTML 页面共享 CSS 和 JavaScript 组件，但消费不同的数据切片。演示版使用静态 JSON，未来系统版用角色受控 API 替换相同的数据接口。

**Tech Stack:** Python 3、openpyxl、标准库 `unittest`、HTML5、CSS3、原生 JavaScript、Chart.js 4.4.0、Python `http.server`。

## Global Constraints

- Apple FY26 Q4 为 2026 年 7 月至 9 月，7 月结束时的时间进度为 33.3%。
- 互动量 = 点赞 + 收藏 + 评论；分享数单列，不计入 KPI。
- 核心经销商 KPI 账号与新增门店账号必须分层分析。
- 原始 Excel 只读，所有标准化结果输出到 `笔记报告/insight/generated/`。
- 每月唯一刷新入口为 `build_insight.py --month YYYY-MM`；页面的指标、状态、排行、诊断和建议全部由构建结果驱动，不得在 HTML/JavaScript 中硬编码业务值或结论。
- 构建结果必须包含 `source_month`、源文件清单、`generated_at` 和质量状态；同月源文件歧义或必需源缺失时构建失败并给出明确错误。
- 两个页面必须共享指标定义、状态阈值、设计令牌和格式化函数。
- 演示版允许经销商选择器；系统版权限必须由后端数据范围控制。
- 状态阈值：领先 >= +10pp；正常为 -5pp 至 +10pp；预警为 -15pp 至 -5pp；严重落后 < -15pp。
- 当前工作区不是 Git 仓库；每个任务以测试、结构检查或浏览器验证作为完成检查点，不执行 Git 提交。

---

## File Structure

```text
笔记报告/
  insight/
    index.html                         # 演示入口
    dealer_insight.html                # 经销商视角
    apple_insight.html                 # Apple 视角
    assets/
      insight.css                      # 共享设计令牌和响应式布局
      insight-core.js                  # 数据加载、格式化、筛选和通用组件
      dealer-dashboard.js              # 经销商页面渲染与交互
      apple-dashboard.js               # Apple 页面渲染与交互
    config/
      category_mapping.json            # 旧分类到统一分类
      region_overrides.json            # 城市人工覆盖
    generated/
      insight_data.json                # 构建后的共享数据产物
      quality_report.json              # 数据质量与覆盖率
    scripts/
      build_insight.py                 # Excel 读取、标准化、聚合与导出
    tests/
      test_build_insight.py            # 纯函数和小型集成测试
```

## Task 1: 建立指标与标准化核心

**Files:**
- Create: `笔记报告/insight/scripts/build_insight.py`
- Create: `笔记报告/insight/tests/test_build_insight.py`

**Interfaces:**
- Produces: `normalize_text(value) -> str`
- Produces: `safe_number(value) -> float`
- Produces: `calculate_kpi_status(actual, target, elapsed_ratio) -> dict`
- Produces: `calculate_content_metrics(values) -> dict`
- Consumes: no project code.

- [ ] **Step 1: Write failing KPI and metric tests**

```python
import unittest

from scripts.build_insight import (
    calculate_content_metrics,
    calculate_kpi_status,
    normalize_text,
)


class MetricTests(unittest.TestCase):
    def test_normalize_text_collapses_whitespace(self):
        self.assertEqual(normalize_text("  ONEZERO\n"), "ONEZERO")

    def test_kpi_status_uses_apple_q4_pacing(self):
        result = calculate_kpi_status(400, 1000, 1 / 3)
        self.assertAlmostEqual(result["completion_rate"], 0.4)
        self.assertAlmostEqual(result["pacing_gap"], 0.4 - 1 / 3)
        self.assertEqual(result["status"], "normal")

    def test_kpi_status_rejects_missing_target(self):
        result = calculate_kpi_status(400, 0, 1 / 3)
        self.assertIsNone(result["completion_rate"])
        self.assertEqual(result["status"], "unmatched")

    def test_content_metrics_use_defined_interactions(self):
        result = calculate_content_metrics({
            "reads": 1000,
            "likes": 50,
            "collects": 20,
            "comments": 10,
            "shares": 99,
            "new_fans": 8,
            "visitors": 40,
            "notes": 5,
        })
        self.assertEqual(result["interactions"], 80)
        self.assertAlmostEqual(result["interaction_rate"], 0.08)
        self.assertAlmostEqual(result["fans_per_10k_reads"], 80)
        self.assertAlmostEqual(result["reads_per_note"], 200)
```

- [ ] **Step 2: Run tests and confirm the missing-module failure**

Run:

```powershell
& 'C:\Users\16154\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s '笔记报告\insight\tests' -v
```

Expected: FAIL because `scripts.build_insight` does not exist.

- [ ] **Step 3: Implement normalization and metric functions**

```python
from __future__ import annotations

from typing import Any


def normalize_text(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def safe_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def calculate_kpi_status(actual: float, target: float, elapsed_ratio: float) -> dict:
    actual_value = safe_number(actual)
    target_value = safe_number(target)
    if target_value <= 0:
        return {"actual": actual_value, "target": target_value,
                "completion_rate": None, "pacing_gap": None,
                "status": "unmatched"}
    completion = actual_value / target_value
    gap = completion - elapsed_ratio
    if gap >= 0.10:
        status = "leading"
    elif gap >= -0.05:
        status = "normal"
    elif gap >= -0.15:
        status = "warning"
    else:
        status = "critical"
    return {"actual": actual_value, "target": target_value,
            "completion_rate": completion, "pacing_gap": gap,
            "status": status}


def calculate_content_metrics(values: dict) -> dict:
    reads = safe_number(values.get("reads"))
    notes = safe_number(values.get("notes"))
    interactions = sum(safe_number(values.get(key))
                       for key in ("likes", "collects", "comments"))
    return {
        "reads": reads,
        "notes": notes,
        "interactions": interactions,
        "reads_per_note": reads / notes if notes else None,
        "interaction_rate": interactions / reads if reads else None,
        "fans_per_10k_reads": safe_number(values.get("new_fans")) / reads * 10000 if reads else None,
        "visitor_rate": safe_number(values.get("visitors")) / reads if reads else None,
        "shares": safe_number(values.get("shares")),
    }
```

- [ ] **Step 4: Re-run unit tests**

Expected: all four tests PASS.

## Task 2: 建立分类、账号和城市标准化

**Files:**
- Create: `笔记报告/insight/config/category_mapping.json`
- Create: `笔记报告/insight/config/region_overrides.json`
- Modify: `笔记报告/insight/scripts/build_insight.py`
- Modify: `笔记报告/insight/tests/test_build_insight.py`

**Interfaces:**
- Consumes: `normalize_text` from Task 1.
- Produces: `map_category(raw_category, mapping) -> tuple[str, bool]`
- Produces: `resolve_region(dealer, store, account, overrides) -> dict`
- Produces: `classify_account_cohort(author_id, kpi_ids) -> str`

- [ ] **Step 1: Add classification tests**

```python
def test_category_mapping_preserves_unclassified(self):
    mapping = {"iPhone 产品": "产品种草"}
    self.assertEqual(map_category("iPhone 产品", mapping), ("产品种草", True))
    self.assertEqual(map_category("", mapping), ("未分类", False))
    self.assertEqual(map_category("新标签", mapping), ("其他", False))

def test_region_override_is_authoritative(self):
    overrides = {"63046732655": {"city": "长春", "province": "吉林", "region": "东北"}}
    result = resolve_region("北京居然智慧家", "长春砂之船店", "63046732655", overrides)
    self.assertEqual(result["city"], "长春")
    self.assertEqual(result["confidence"], "confirmed")

def test_kpi_account_is_core_cohort(self):
    self.assertEqual(classify_account_cohort("author-1", {"author-1"}), "core_kpi")
    self.assertEqual(classify_account_cohort("author-2", {"author-1"}), "expanded_store")
```

- [ ] **Step 2: Create explicit category mapping**

The JSON must include every observed 6 月 and 7 月 category, including spelling variants such as `iPhone产品`, `mac 产品`, `IP活动`, and `beats 内容`. Each value has this shape:

```json
{
  "iPhone 产品": {"unified": "产品种草", "version": "2026-08", "confirmed": true},
  "产品功能": {"unified": "产品功能与使用技巧", "version": "2026-08", "confirmed": true},
  "门店服务/体验": {"unified": "门店服务与体验", "version": "2026-08", "confirmed": true},
  "产品种草": {"unified": "产品种草", "version": "2026-08", "confirmed": true}
}
```

- [ ] **Step 3: Create the region override shell and resolver**

Start `region_overrides.json` as `{}`. `resolve_region` first checks account-name, account-ID, and author-ID aliases in that order, then extracts a known city token from dealer/store text, otherwise returns:

```python
{"city": "待补充区域", "province": "", "region": "", "confidence": "unknown"}
```

- [ ] **Step 4: Run classification tests**

Expected: all Task 1 and Task 2 tests PASS.

## Task 3: 读取 Excel 并生成质量报告

**Files:**
- Modify: `笔记报告/insight/scripts/build_insight.py`
- Modify: `笔记报告/insight/tests/test_build_insight.py`
- Create: `笔记报告/insight/generated/quality_report.json`

**Interfaces:**
- Consumes: project Excel files and Task 2 standardizers.
- Produces: `read_monthly_accounts(path, sheet_name, month) -> list[dict]`
- Produces: `read_notes(path, sheet_name, snapshot_date) -> list[dict]`
- Produces: `read_kpi(path, quarter) -> list[dict]`
- Produces: `profile_quality(accounts, notes, kpis) -> dict`

- [ ] **Step 1: Add a temporary-workbook integration test**

Create a workbook in `tempfile.TemporaryDirectory()` with the same 19-column monthly account header, write one account row, read it through `read_monthly_accounts`, and assert the author ID, account name, reads, and report month.

```python
def test_read_monthly_accounts_uses_header_names(self):
    # Build a minimal workbook whose columns match the source labels.
    rows = [["序号", "经销商名称", "门店名称", "小红书账号名称", "小红书号",
             "小红书作者ID", "笔记条数", "总浏览", "新增粉丝", "点赞", "收藏",
             "评论", "主页访客数"],
            [1, "测试经销商", "测试门店", "测试账号", "10001", "author-1",
             5, 1000, 8, 50, 20, 10, 40]]
    path = make_workbook(rows)
    result = read_monthly_accounts(path, "Sheet1", "2026-07")
    self.assertEqual(result[0]["author_id"], "author-1")
    self.assertEqual(result[0]["reads"], 1000)
```

- [ ] **Step 2: Implement header-based readers**

Readers must locate columns by normalized header text rather than fixed indexes. Accept the known aliases `时间/导出数据时间`, `阅读次数/累计阅读数`, and `笔记形式/笔记类型`.

- [ ] **Step 3: Implement the quality profile**

The report must include:

```python
{
    "generated_at": "ISO-8601 timestamp",
    "account_rows": 246,
    "unique_author_ids": 246,
    "kpi_accounts": 55,
    "kpi_matched_accounts": 54,
    "kpi_match_rate": 54 / 55,
    "duplicate_note_ids": 0,
    "category_completeness": 1 - 64 / 48236,
    "city_identification_rate": "calculated value",
    "warnings": ["core account scope changed between June and July"]
}
```

- [ ] **Step 4: Run the builder against source files**

Run:

```powershell
& 'C:\Users\16154\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' '笔记报告\insight\scripts\build_insight.py' --month 2026-07 --quality-only
```

Expected: `generated/quality_report.json` exists, parses as JSON, and reports 55 Q4 KPI accounts with 54 matched July accounts.

## Task 4: 构建共享 Insight 数据模型

**Files:**
- Modify: `笔记报告/insight/scripts/build_insight.py`
- Modify: `笔记报告/insight/tests/test_build_insight.py`
- Create: `笔记报告/insight/generated/insight_data.json`

**Interfaces:**
- Consumes: readers and quality profile from Task 3.
- Produces: `build_dealer_insights(...) -> list[dict]`
- Produces: `build_apple_insights(...) -> dict`
- Produces JSON schema version `1.0`.

- [ ] **Step 1: Add aggregation tests**

Test that dealer KPI actuals use July account values, target completion uses FY26 Q4 target, and shares are excluded from interactions. Test that Apple status counts equal the number of matched KPI accounts.

- [ ] **Step 2: Implement dealer-level aggregation**

Each dealer record must contain:

```json
{
  "dealer_id": "stable slug",
  "dealer_name": "经销商名称",
  "cohort": "core_kpi",
  "data_freshness": "2026-08-01",
  "kpis": {"reads": {}, "interactions": {}, "fans": {}},
  "content_summary": {},
  "category_performance": [],
  "city_performance": [],
  "account_performance": [],
  "recommendations": []
}
```

Recommendations use `confidence` values `supported`, `signal`, or `validate` and include the metric evidence used.

- [ ] **Step 3: Implement Apple-level aggregation**

Include target-weighted network KPI completion, unweighted dealer status distribution, cohort counts, regional summaries, category structure, dealer quadrants, risk list, replicable cases, and data-quality metadata.

- [ ] **Step 4: Build and validate JSON**

Run the builder without flags. Then use Python `json.load` to assert:

- `schema_version == "1.0"`
- `source_month == "2026-07"` and every generated recommendation includes machine-generated evidence
- dealer records exist
- three network KPI objects exist
- dealer status counts sum to matched KPI accounts
- no `NaN` or `Infinity` values are serialized
- building the same source month twice produces identical analytical content aside from `generated_at`

## Task 5: 建立共享看板外壳

**Files:**
- Create: `笔记报告/insight/assets/insight.css`
- Create: `笔记报告/insight/assets/insight-core.js`
- Create: `笔记报告/insight/index.html`

**Interfaces:**
- Consumes: `generated/insight_data.json`.
- Produces: `InsightCore.loadData()`, `formatNumber()`, `formatPercent()`, `statusLabel()`, `renderMetricCard()`, and `chartTheme()`.

- [ ] **Step 1: Create the demo entry page**

The entry page provides two clear links, the shared data freshness date, and no marketing hero. It uses the same sidebar/header shell as the dashboards.

- [ ] **Step 2: Define design tokens and responsive layout**

Use exact tokens:

```css
:root {
  --bg: #eef1f3;
  --surface: #ffffff;
  --ink: #1d1d1f;
  --muted: #6e6e73;
  --line: #dfe3e6;
  --nav: #151515;
  --positive: #30b85a;
  --warning: #e59a16;
  --critical: #d94141;
  --radius: 8px;
  --sidebar-width: 220px;
}
```

At widths below 1024px collapse the sidebar to an icon/compact header. At 390px use a single-column content flow and horizontally scroll only dense data tables.

- [ ] **Step 3: Implement shared JavaScript utilities**

`loadData()` fetches `generated/insight_data.json`, checks `schema_version`, and renders a visible error state if loading fails. Metric cards reserve stable height and never resize when values change.

No page module may contain hard-coded operating totals, rankings, status labels, or recommendation sentences. It may only contain presentation labels and rendering templates populated from generated JSON.

- [ ] **Step 4: Run a static structure check**

Verify all local CSS/JS/JSON references return HTTP 200 from the existing local server and no inline hard-coded business datasets remain in HTML.

## Task 6: 实现经销商视角

**Files:**
- Create: `笔记报告/insight/dealer_insight.html`
- Create: `笔记报告/insight/assets/dealer-dashboard.js`

**Interfaces:**
- Consumes: `data.dealers[]` and shared utilities from Task 5.
- Produces: dealer selector, KPI cards, category matrix, account/city tables, and recommendation list.

- [ ] **Step 1: Build semantic page sections**

Create `overview`, `kpi-progress`, `content-strategy`, `city-accounts`, and `actions` sections. The first viewport contains filters, three KPI cards, five operating metrics, and one concise summary.

- [ ] **Step 2: Implement dealer selection and filters**

Filter state includes dealer, month, city, account, format, and unified category. Changing a filter rerenders only dependent modules and updates the visible data-scope label.

- [ ] **Step 3: Implement charts and evidence panels**

- KPI: horizontal target/pacing bullet bars.
- Content: category supply-versus-efficiency scatter.
- Format: image/video grouped bars.
- Region: city/account heatmap or ranked table depending on data coverage.

Every visual has adjacent takeaway text and a visible scope/denominator.

- [ ] **Step 4: Implement action recommendations**

Render recommendation, evidence, confidence, priority city/account, and suggested publishing mix. Do not present a recommendation when its minimum sample threshold fails.

- [ ] **Step 5: Verify dealer data isolation**

After selecting a dealer, inspect page text and chart datasets to confirm no other dealer's account-level rows are rendered. Peer examples may show a public benchmark label but not browsable peer details.

## Task 7: 实现 Apple 视角

**Files:**
- Create: `笔记报告/insight/apple_insight.html`
- Create: `笔记报告/insight/assets/apple-dashboard.js`

**Interfaces:**
- Consumes: `data.apple` and shared utilities from Task 5.
- Produces: network KPI summary, status distribution, dealer quadrants, region/category diagnostics, drilldown table, and Apple actions.

- [ ] **Step 1: Build semantic page sections**

Create `network-overview`, `kpi-health`, `dealer-segments`, `regional-content`, and `operating-actions` sections.

- [ ] **Step 2: Implement network KPI and risk distribution**

Show target-weighted completion for reads, interactions, and fans; separately show counts of leading, normal, warning, critical, and unmatched accounts.

- [ ] **Step 3: Implement dealer and region diagnostics**

- Four-quadrant scatter based on normalized supply and efficiency.
- KPI risk ranking with completion, pacing gap, and cohort.
- Region/city heatmap with coverage count.
- Category-mix comparison by region and cohort.

- [ ] **Step 4: Implement management actions**

Group actions into `立即行动`, `下月验证`, and `季度规划`. Each action links to the affected dealer/region/category evidence in the page.

- [ ] **Step 5: Reconcile drilldown totals**

Use JavaScript assertions in development mode to confirm dealer-row sums/counts reconcile with network cards and status totals.

## Task 8: 端到端验证与本地交付

**Files:**
- Modify only files found defective during verification.

**Interfaces:**
- Consumes: complete static site and generated JSON.
- Produces: verified local demo URLs.

- [ ] **Step 1: Run all Python tests and rebuild data**

Expected: all tests PASS, builder exits 0, both generated JSON files parse successfully.

- [ ] **Step 2: Verify HTTP delivery**

Check:

```text
http://127.0.0.1:8000/insight/index.html
http://127.0.0.1:8000/insight/dealer_insight.html
http://127.0.0.1:8000/insight/apple_insight.html
```

Expected: HTTP 200 for all pages, assets, and JSON.

- [ ] **Step 3: Run browser verification**

Inspect both dashboards at 1440x900, 1024x768, and 390x844. Confirm no horizontal page overflow, clipped filters, blank charts, overlapping text, console errors, or inaccessible focus states.

- [ ] **Step 4: Validate representative business values**

Spot-check at least five matched KPI accounts against FY26 Q4 targets and July actuals. Verify the Apple page status counts reconcile to 54 matched accounts and separately identifies the unmatched account.

- [ ] **Step 5: Confirm graceful degradation**

Block Chart.js once and verify KPI cards, textual conclusions, recommendations, and data tables remain readable.

- [ ] **Step 6: Keep the local server running**

Reuse port 8000 when available. Record the server PID and provide the three local URLs to the user.
