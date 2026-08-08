import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const dashboardPath = new URL("../assets/apple-dashboard.js", import.meta.url);
const pagePath = new URL("../apple_insight.html", import.meta.url);
const cssPath = new URL("../assets/insight.css", import.meta.url);
const insightDataPath = new URL("../generated/insight_data.json", import.meta.url);

const core = {
  formatNumber: (value) => value == null ? "—" : `N:${value}`,
  formatPercent: (value) => value == null ? "—" : `P:${value}`,
  formatSignedPoints: (value) => value == null ? "—" : `S:${value}`,
  statusLabel: (value) => `L:${value}`,
  statusClass: (value) => `C:${value}`,
};

async function loadDashboard() {
  const source = await readFile(dashboardPath, "utf8");
  const window = {};
  const context = vm.createContext({
    console,
    Intl,
    Map,
    Number,
    Object,
    Set,
    window,
  });

  vm.runInContext(source, context, { filename: "apple-dashboard.js" });
  return window.AppleDashboard;
}

async function runDashboardPage(payloadOrError, options = {}) {
  const source = await readFile(dashboardPath, "utf8");
  const page = await readFile(pagePath, "utf8");
  const elements = {};
  for (const match of page.matchAll(/<[^>]*\sid="([^"]+)"[^>]*>/g)) {
    const tag = match[0];
    const datasetMatch = tag.match(/data-filter-key="([^"]+)"/);
    elements[match[1]] = {
      className: "",
      dataset: datasetMatch ? { filterKey: datasetMatch[1] } : {},
      hidden: /\shidden(?:\s|>)/.test(tag),
      innerHTML: "",
      textContent: "",
      addEventListener: () => {},
    };
  }
  const filterControls = Object.values(elements).filter((element) => element.dataset.filterKey);
  const dashboardSections = [...page.matchAll(/<[^>]*\sid="([^"]+)"[^>]*data-apple-content[^>]*>/g)]
    .map((match) => elements[match[1]]);
  const document = {
    readyState: "complete",
    getElementById: (id) => elements[id] || null,
    querySelectorAll: (selector) => selector === "[data-filter-key]" ? filterControls : selector === "[data-apple-content]" ? dashboardSections : [],
  };
  const pageCore = {
    ...core,
    chartTheme: () => ({ colors: {}, grid: {}, ticks: {} }),
    destroyCharts: (charts) => {
      Object.values(charts || {}).forEach((chart) => {
        if (chart && typeof chart.destroy === "function") {
          chart.destroy();
        }
      });
    },
    escapeHtml: (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;"),
    initIcons: () => false,
    loadData: async () => {
      if (payloadOrError instanceof Error) {
        throw payloadOrError;
      }
      return payloadOrError;
    },
    renderError: (target, error) => { target.innerHTML = `<div role="alert">${error.message}</div>`; },
    renderLoading: (target) => { target.innerHTML = `<div role="status">loading</div>`; },
    renderMetricCard: ({ label, value }) => `<article>${label}:${value}</article>`,
  };
  const window = { document, InsightCore: pageCore, location: { hostname: "localhost" }, ...options.window };
  const context = vm.createContext({ console, Date, document, Intl, Map, Number, Object, Set, window });

  vm.runInContext(source, context, { filename: "apple-dashboard.js" });
  await new Promise((resolve) => setImmediate(resolve));
  return { elements, dashboardSections };
}

function makeApple(overrides = {}) {
  const base = {
    source_month: "2026-07",
    network_kpis: {
      reads: { actual: 900, target: 1800, completion_rate: 0.5, pacing_gap: 0.167, status: "leading" },
      interactions: { actual: 80, target: 200, completion_rate: 0.4, pacing_gap: 0.067, status: "normal" },
      fans: { actual: 10, target: 60, completion_rate: 1 / 6, pacing_gap: -1 / 6, status: "critical" },
    },
    status_counts: { leading: 1, normal: 0, warning: 1, critical: 1, unmatched: 0 },
    account_counts: { core_kpi: 3, expanded_store: 2 },
    dealer_quadrants: [
      { dealer_id: "d-core-risk", name: "核心风险经销商", cohort: "core_kpi", normalized_supply: 0.5, normalized_efficiency: 0.4, quadrant: "low_supply_low_efficiency" },
      { dealer_id: "d-core-good", name: "核心优秀经销商", cohort: "core_kpi", normalized_supply: 2, normalized_efficiency: 3, quadrant: "high_supply_high_efficiency" },
      { dealer_id: "d-store", name: "扩展门店经销商", cohort: "expanded_store", normalized_supply: 1.2, normalized_efficiency: 0.7, quadrant: "high_supply_low_efficiency" },
    ],
    regional_summaries: [
      { region: "华东", account_count: 3, identified_coverage: 1 },
      { region: "华南", account_count: 2, identified_coverage: 0.5 },
    ],
    city_summaries: [
      { city: "上海", account_count: 2, identified_coverage: 1 },
      { city: "深圳", account_count: 1, identified_coverage: 1 },
    ],
    category_mix_performance: [
      { region: "华东", cohort: "core_kpi", category: "产品种草", notes: 8, reads: 800, interactions: 80, new_fans: 8, reads_per_note: 100, interaction_rate: 0.1, fans_per_10k_reads: 100 },
      { region: "华东", cohort: "expanded_store", category: "产品种草", notes: 4, reads: 200, interactions: 10, new_fans: 1, reads_per_note: 50, interaction_rate: 0.05, fans_per_10k_reads: 50 },
      { region: "华南", cohort: "core_kpi", category: "营销活动", notes: 5, reads: 300, interactions: 12, new_fans: 2, reads_per_note: 60, interaction_rate: 0.04, fans_per_10k_reads: 66.7 },
    ],
    risk_dealers: [
      { dealer_id: "d-core-risk", name: "核心风险经销商", status: "critical" },
      { dealer_id: "d-store", name: "扩展门店经销商", status: "warning" },
      { dealer_id: "d-missing", name: "契约未关联经销商", status: "warning" },
    ],
    replicable_cases: {
      category: [
        { dealer_id: "d-core-good", cohort: "core_kpi", category: "产品种草", evidence: [{ metric: "reads_per_note", value: 100, benchmark: 50, scope: "dealer_category" }] },
      ],
      city: [
        { city: "上海", region: "华东", cohort: "core_kpi", dealer_ids: ["d-core-good"], evidence: [{ metric: "notes", value: 8, benchmark: 3, scope: "city_content" }] },
      ],
      account: [
        { dealer_id: "d-core-good", account_id: "a-1", evidence: [{ metric: "kpi_status", value: 1, benchmark: 0, scope: "core_kpi" }] },
      ],
    },
    actions: {
      "立即行动": [
        {
          id: "action-kpi",
          rule_id: "kpi_fans_critical",
          type: "kpi",
          title: "生成器 KPI 行动",
          action: "生成器 KPI 文案",
          confidence: "supported",
          priority: "high",
          region: "华东",
          cohort: "core_kpi",
          affected_dealer_count: 2,
          affected_account_count: 3,
          evidence: [{ metric: "fans_pacing_gap", value: -0.2, benchmark: 0, scope: "network_action" }],
          target: { category: "", city: "", account_id: "" },
          top_examples: [{ dealer_id: "d-core-risk", dealer_name: "核心风险经销商", recommendation_id: "r-1", evidence: [] }],
          drilldown_recommendation_ids: ["r-1", 'trace<unsafe>&"'],
        },
      ],
      "下月验证": [
        {
          id: "action-category",
          rule_id: "category_scale",
          type: "category",
          title: "生成器分类行动",
          action: "生成器分类文案",
          confidence: "validate",
          priority: "medium",
          region: "multi_region",
          cohort: "core_kpi",
          affected_dealer_count: 1,
          affected_account_count: 0,
          evidence: [{ metric: "note_share", value: 0.1, benchmark: 0.2, scope: "aggregated_recommendations" }],
          target: { category: "产品种草", city: "", account_id: "" },
          top_examples: [{ dealer_id: "d-core-good", dealer_name: "核心优秀经销商", recommendation_id: "r-2", evidence: [] }],
          drilldown_recommendation_ids: ["r-2"],
        },
      ],
      "季度规划": [],
    },
    quality_metadata: { matched_kpi_accounts: 3, unmatched_kpi_accounts: 1, data_freshness: "monthly_snapshot" },
  };

  return { ...base, ...overrides };
}

test("filter options come from the Apple contract", async () => {
  const dashboard = await loadDashboard();
  const options = dashboard.getFilterOptions(makeApple());

  assert.deepEqual([...options.regions], ["华东", "华南"]);
  assert.deepEqual([...options.cohorts], ["core_kpi", "expanded_store"]);
  assert.deepEqual([...options.categories], ["产品种草", "营销活动"]);
  assert.deepEqual([...options.statuses], ["leading", "normal", "warning", "critical", "unmatched"]);
});

test("region cohort and category filters compose without mutating generated rows", async () => {
  const dashboard = await loadDashboard();
  const apple = makeApple();
  const original = structuredClone(apple.category_mix_performance);

  const rows = dashboard.filterCategoryPerformance(apple.category_mix_performance, {
    region: "华东",
    cohort: "core_kpi",
    category: "产品种草",
  });

  assert.equal(rows.length, 1);
  assert.equal(rows[0].reads, 800);
  assert.deepEqual(apple.category_mix_performance, original);
  assert.deepEqual(
    dashboard.filterRegionalSummaries(apple.regional_summaries, "华南").map((row) => row.region),
    ["华南"],
  );
});

test("cohort and status filters select quadrants and ranked risks using contract joins", async () => {
  const dashboard = await loadDashboard();
  const apple = makeApple();

  assert.deepEqual(
    dashboard.filterDealerQuadrants(apple.dealer_quadrants, { cohort: "expanded_store" }).map((row) => row.dealer_id),
    ["d-store"],
  );

  const risks = dashboard.selectRiskDealers(apple.risk_dealers, apple.dealer_quadrants, {
    cohort: "core_kpi",
    status: "critical",
  });
  assert.deepEqual(risks.map((row) => row.dealer_id), ["d-core-risk"]);
  assert.equal(risks[0].cohort, "core_kpi");
  assert.equal(risks[0].rank, 1);
});

test("risk table displays generator worst pacing gaps and preserves generated order", async () => {
  const apple = makeApple({
    risk_dealers: [
      { dealer_id: "d-store", name: "生成顺序第一", status: "warning", worst_pacing_gap: -0.1 },
      { dealer_id: "d-core-risk", name: "生成顺序第二", status: "critical", worst_pacing_gap: -0.9 },
    ],
  });
  const dashboard = await loadDashboard();
  const selected = dashboard.selectRiskDealers(apple.risk_dealers, apple.dealer_quadrants, {});
  const { elements } = await runDashboardPage({ source_month: "2026-07", generated_at: "2026-08-08T12:00:00Z", apple });
  const html = elements["risk-table"].innerHTML;

  assert.deepEqual(selected.map((item) => [item.name, item.rank, item.worst_pacing_gap]), [
    ["生成顺序第一", 1, -0.1],
    ["生成顺序第二", 2, -0.9],
  ]);
  assert.match(html, /最差节奏偏差/);
  assert.match(html, /S:-0\.1/);
  assert.match(html, /S:-0\.9/);
  assert.equal(html.indexOf("生成顺序第一") < html.indexOf("生成顺序第二"), true);
});

test("quadrant chart series never merge core KPI and expanded-store dealers", async () => {
  const dashboard = await loadDashboard();
  const series = dashboard.buildQuadrantSeries(makeApple().dealer_quadrants);

  assert.equal(series.length, 3);
  assert.equal(series.every((item) => new Set(item.rows.map((row) => row.cohort)).size === 1), true);
  assert.equal(series.some((item) => item.cohort === "core_kpi"), true);
  assert.equal(series.some((item) => item.cohort === "expanded_store"), true);
});

test("weighted KPI cards format only generated actual target completion pacing and status", async () => {
  const dashboard = await loadDashboard();
  const cards = dashboard.buildNetworkKpiViewModel(makeApple().network_kpis, core);

  assert.equal(cards.length, 3);
  assert.deepEqual(
    {
      key: cards[0].key,
      actual: cards[0].actual,
      target: cards[0].target,
      completion: cards[0].completion,
      pacingGap: cards[0].pacingGap,
      status: cards[0].status,
    },
    { key: "reads", actual: "N:900", target: "N:1800", completion: "P:0.5", pacingGap: "S:0.167", status: "leading" },
  );
});

test("core KPI and expanded-store scope remain separate", async () => {
  const dashboard = await loadDashboard();
  const scope = dashboard.buildScopeViewModel(makeApple(), core);

  assert.deepEqual(
    { core: scope.coreKpiAccounts, expanded: scope.expandedStoreAccounts, matched: scope.matchedKpiAccounts, unmatched: scope.unmatchedKpiAccounts },
    { core: "N:3", expanded: "N:2", matched: "N:3", unmatched: "N:1" },
  );
  assert.equal("target" in scope.expandedStore, false);
  assert.equal("completion" in scope.expandedStore, false);
});

test("action filtering preserves phase rule evidence confidence priority and examples", async () => {
  const dashboard = await loadDashboard();
  const apple = makeApple();
  const original = structuredClone(apple.actions);
  const actions = dashboard.filterActions(apple.actions, { region: "华东", cohort: "core_kpi", category: "产品种草" });

  assert.deepEqual([...actions].map((item) => item.id), ["action-kpi", "action-category"]);
  assert.equal(actions[0].phase, "立即行动");
  assert.equal(actions[0].rule_id, "kpi_fans_critical");
  assert.equal(actions[0].confidence, "supported");
  assert.equal(actions[0].priority, "high");
  assert.equal(actions[0].evidence[0].scope, "network_action");
  assert.equal(actions[0].top_examples[0].recommendation_id, "r-1");
  assert.deepEqual(apple.actions, original);
});

test("action rendering exposes every drilldown recommendation id in order and escapes HTML", async () => {
  const { elements } = await runDashboardPage({ source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z", apple: makeApple() });
  const html = elements["action-phases"].innerHTML;
  const escapedNonTopId = "trace&lt;unsafe&gt;&amp;&quot;";

  assert.match(html, /完整追溯 ID/);
  assert.match(html, /r-1/);
  assert.match(html, new RegExp(escapedNonTopId));
  assert.doesNotMatch(html, /trace<unsafe>/);
  assert.equal(html.indexOf("r-1") < html.indexOf(escapedNonTopId), true);
});

test("real Apple actions render all generated drilldown recommendation ids in source order", async () => {
  const data = JSON.parse(await readFile(insightDataPath, "utf8"));
  const actions = Object.values(data.apple.actions).flat();
  const recommendationIds = actions.flatMap((item) => item.drilldown_recommendation_ids || []);
  const { elements } = await runDashboardPage(data);
  const html = elements["action-phases"].innerHTML;

  assert.equal(actions.length, 36);
  assert.equal(recommendationIds.length, 243);
  assert.equal((html.match(/class="apple-drilldown-ids"/g) || []).length, actions.length);
  assert.equal((html.match(/<li><code>/g) || []).length, recommendationIds.length);

  let offset = -1;
  for (const recommendationId of recommendationIds) {
    offset = html.indexOf(`<li><code>${recommendationId}</code></li>`, offset + 1);
    assert.notEqual(offset, -1, `missing or reordered recommendation id: ${recommendationId}`);
  }
});

test("replicable selections respect only dimensions present in each generated case", async () => {
  const dashboard = await loadDashboard();
  const cases = dashboard.filterReplicableCases(makeApple().replicable_cases, {
    region: "华东",
    cohort: "core_kpi",
    category: "产品种草",
  });

  assert.deepEqual(cases.category.map((item) => item.dealer_id), ["d-core-good"]);
  assert.deepEqual(cases.city.map((item) => item.city), ["上海"]);
  assert.equal(cases.account.length, 0);
  assert.equal(cases.category[0].evidence[0].scope, "dealer_category");
});

test("status totals reconcile to the core KPI account count", async () => {
  const dashboard = await loadDashboard();
  const apple = makeApple();

  assert.deepEqual(JSON.parse(JSON.stringify(dashboard.reconcileAppleContract(apple))), { ok: true, statusTotal: 3, coreKpiAccounts: 3 });
  assert.equal(dashboard.reconcileAppleContract(makeApple({ account_counts: { core_kpi: 4, expanded_store: 2 } })).ok, false);
});

test("complete Apple view model is sourced from top-level apple and keeps empty arrays stable", async () => {
  const dashboard = await loadDashboard();
  const data = { source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z", apple: makeApple() };
  const viewModel = dashboard.buildAppleViewModel(data, { region: "华东", cohort: "core_kpi", category: "产品种草", status: "critical" }, core);

  assert.equal(viewModel.sourceMonth, "2026-07");
  assert.equal(viewModel.kpis.length, 3);
  assert.deepEqual(viewModel.risks.map((item) => item.dealer_id), ["d-core-risk"]);
  assert.equal(viewModel.categories.length, 1);
  assert.equal(viewModel.actions.length, 2);

  const empty = dashboard.buildAppleViewModel({ source_month: "2026-07", apple: {} }, {}, core);
  assert.deepEqual(JSON.parse(JSON.stringify({
    quadrants: empty.quadrants,
    risks: empty.risks,
    regions: empty.regions,
    cities: empty.cities,
    categories: empty.categories,
    actions: empty.actions,
  })), { quadrants: [], risks: [], regions: [], cities: [], categories: [], actions: [] });
  assert.equal(dashboard.buildAppleViewModel({ source_month: "2026-07" }, {}, core), null);
});

test("Apple page labels source snapshot freshness instead of build time", async () => {
  const sourceSnapshot = "2026-08-01T00:00:00Z";
  const generatedAt = "2026-08-08T12:00:00Z";
  const dataFreshness = { source_snapshot_at: sourceSnapshot, basis: "note_export_timestamp", is_fallback: false };
  const payload = {
    source_month: "2026-07",
    generated_at: generatedAt,
    metadata: { data_freshness: dataFreshness },
    apple: makeApple({ quality_metadata: { matched_kpi_accounts: 3, unmatched_kpi_accounts: 1, data_freshness: dataFreshness } }),
  };
  const { elements } = await runDashboardPage(payload);
  const dashboard = await loadDashboard();
  const formatter = new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

  assert.equal(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(sourceSnapshot))}`);
  assert.notEqual(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(generatedAt))}`);
  assert.equal(dashboard.buildAppleViewModel(payload, {}, core).dataFreshness.source_snapshot_at, sourceSnapshot);
});

test("Apple page exposes semantic sections and visible failure fallbacks", async () => {
  const source = await readFile(pagePath, "utf8");

  for (const id of ["network-overview", "kpi-health", "dealer-segments", "regional-content", "operating-actions"]) {
    assert.match(source, new RegExp(`id=["']${id}["']`));
  }
  assert.match(source, /id="data-state"[^>]*aria-live="polite"/);
  assert.match(source, /id="dashboard-content"[^>]*hidden/);
  assert.match(source, /id="quadrant-fallback"/);
  assert.match(source, /id="status-fallback"/);
  assert.match(source, /assets\/apple-dashboard\.js/);
});

test("Apple chart fallbacks honor the hidden attribute when charts are available", async () => {
  const css = await readFile(cssPath, "utf8");
  assert.match(css, /\.apple-page\s+\.chart-fallback\[hidden\]\s*{[^}]*display:\s*none/s);
});

test("missing Chart.js keeps the dashboard visible with textual chart fallbacks", async () => {
  const { elements } = await runDashboardPage({ source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z", apple: makeApple() });

  assert.equal(elements["dashboard-content"].hidden, false);
  assert.equal(elements["status-fallback"].hidden, false);
  assert.equal(elements["quadrant-fallback"].hidden, false);
  assert.equal(elements["category-fallback"].hidden, false);
  assert.match(elements["risk-table"].innerHTML, /核心风险经销商/);
});

test("Chart constructor failures destroy partial charts and leave data plus all fallbacks visible", async () => {
  const chartState = { calls: 0, destroyed: 0 };
  function ThrowingChart() {
    chartState.calls += 1;
    if (chartState.calls === 2) {
      throw new Error("fixture chart constructor failed");
    }
    return { destroy: () => { chartState.destroyed += 1; } };
  }

  const { elements, dashboardSections } = await runDashboardPage(
    { source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z", apple: makeApple() },
    { window: { Chart: ThrowingChart } },
  );

  assert.equal(chartState.calls, 2);
  assert.equal(chartState.destroyed, 1);
  assert.equal(elements["dashboard-content"].hidden, false);
  assert.equal(dashboardSections.every((section) => !section.hidden), true);
  assert.equal(elements["status-fallback"].hidden, false);
  assert.equal(elements["quadrant-fallback"].hidden, false);
  assert.equal(elements["category-fallback"].hidden, false);
  assert.equal(elements["data-state"].hidden, true);
  assert.equal(elements["data-state"].innerHTML, "");
  assert.match(elements["risk-table"].innerHTML, /核心风险经销商/);
});

test("legal empty and missing Apple contracts produce visible bounded empty states", async () => {
  const legalEmpty = await runDashboardPage({ source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z", apple: {} });
  assert.equal(legalEmpty.elements["dashboard-content"].hidden, false);
  assert.match(legalEmpty.elements["network-kpi-cards"].innerHTML, /没有可显示的网络 KPI/);

  const missing = await runDashboardPage({ source_month: "2026-07", generated_at: "2026-08-06T12:00:00Z" });
  assert.equal(missing.elements["dashboard-content"].hidden, false);
  assert.match(missing.elements["dashboard-content"].innerHTML, /没有可显示的 Apple 网络数据/);
  assert.equal(missing.dashboardSections.every((section) => section.hidden), true);
});

test("data loading errors remain visible and keep dashboard sections hidden", async () => {
  const { elements, dashboardSections } = await runDashboardPage(new Error("fixture load failed"));

  assert.match(elements["data-state"].innerHTML, /role="alert"/);
  assert.match(elements["data-state"].innerHTML, /fixture load failed/);
  assert.equal(elements["dashboard-content"].hidden, true);
  assert.equal(dashboardSections.every((section) => section.hidden), true);
});
