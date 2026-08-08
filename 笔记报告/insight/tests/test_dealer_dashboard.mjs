import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const dashboardPath = new URL("../assets/dealer-dashboard.js", import.meta.url);
const insightDataPath = new URL("../generated/insight_data.json", import.meta.url);
const pagePath = new URL("../dealer_insight.html", import.meta.url);

const core = {
  formatNumber: (value) => value == null ? "-" : `N:${value}`,
  formatPercent: (value) => value == null ? "-" : `P:${value}`,
  formatSignedPoints: (value) => value == null ? "-" : `S:${value}`,
  statusLabel: (value) => `L:${value}`,
  statusClass: (value) => `C:${value}`,
  renderMetricCard: ({ label, value }) => `<article>${label}:${value}</article>`,
};

function makeDealer(overrides = {}) {
  return {
    dealer_id: "dealer-a",
    name: "经销商 A",
    cohort: "core_kpi",
    accounts: [
      {
        author_id: "account-core",
        account_name: "A 核心账号",
        store: "A 总店",
        cohort: "core_kpi",
        city: "上海",
        region: "华东",
        confidence: "confirmed",
        metrics: { reads: 900, likes: 30, collects: 10, comments: 5, shares: 2, new_fans: 8, visitors: 20 },
      },
      {
        author_id: "account-store",
        account_name: "A 扩展门店",
        store: "A 分店",
        cohort: "expanded_store",
        city: "苏州",
        region: "华东",
        confidence: "inferred",
        metrics: { reads: 300, likes: 12, collects: 4, comments: 2, shares: 1, new_fans: 3, visitors: 9 },
      },
    ],
    kpi: {
      reads: { actual: 900, target: 1800, completion_rate: 0.5, pacing_gap: 0.167, status: "leading" },
      interactions: { actual: 45, target: 180, completion_rate: 0.25, pacing_gap: -0.083, status: "warning" },
      fans: { actual: 8, target: 80, completion_rate: 0.1, pacing_gap: -0.233, status: "critical" },
      elapsed_ratio: 0.333,
      account_statuses: [{ author_id: "account-core", status: "critical" }],
      overall_status: "critical",
    },
    expanded_store_metrics: {
      reads: 300,
      notes: 4,
      interactions: 18,
      reads_per_note: 75,
      interaction_rate: 0.06,
      fans_per_10k_reads: 100,
      visitor_rate: 0.03,
      shares: 1,
    },
    content: {
      reads: 1200,
      notes: 10,
      interactions: 63,
      reads_per_note: 120,
      interaction_rate: 0.0525,
      fans_per_10k_reads: 91.7,
      visitor_rate: 0.024,
      shares: 3,
      new_fans: 11,
      methodology_note: "样本口径来自数据",
      image_notes: 6,
      video_notes: 4,
      image_share: 0.6,
      video_share: 0.4,
      categories: [
        { category: "产品种草", notes: 6, note_share: 0.6, reads: 900, reads_per_note: 150, interaction_rate: 0.06, benchmark_note_share: 0.4, benchmark_reads_per_note: 120, benchmark_confidence: "supported", benchmark_sample_size: 9 },
        { category: "营销活动", notes: 4, note_share: 0.4, reads: 300, reads_per_note: 75, interaction_rate: 0.03, benchmark_note_share: 0.5, benchmark_reads_per_note: 100, benchmark_confidence: "supported", benchmark_sample_size: 8 },
      ],
      by_city_cohort: [
        {
          city: "上海",
          region: "华东",
          cohort: "core_kpi",
          content: {
            notes: 6,
            reads: 900,
            interactions: 54,
            new_fans: 8,
            reads_per_note: 150,
            interaction_rate: 0.06,
            fans_per_10k_reads: 88.9,
            visitor_rate: 0.02,
            image_notes: 2,
            video_notes: 4,
            image_share: 1 / 3,
            video_share: 2 / 3,
            categories: [{ category: "产品种草", notes: 6, reads: 900, interactions: 54, new_fans: 8, note_share: 1, reads_per_note: 150, interaction_rate: 0.06 }],
          },
        },
        {
          city: "苏州",
          region: "华东",
          cohort: "expanded_store",
          content: {
            notes: 4,
            reads: 300,
            interactions: 9,
            new_fans: 3,
            reads_per_note: 75,
            interaction_rate: 0.03,
            fans_per_10k_reads: 100,
            visitor_rate: 0.03,
            image_notes: 4,
            video_notes: 0,
            image_share: 1,
            video_share: 0,
            categories: [{ category: "营销活动", notes: 4, reads: 300, interactions: 9, new_fans: 3, note_share: 1, reads_per_note: 75, interaction_rate: 0.03 }],
          },
        },
      ],
    },
    recommendations: [
      { id: "general", type: "kpi", title: "经销商级建议", action: "经销商级动作", confidence: "supported", priority: "high", evidence: [], target: { category: "", city: "", account_id: "" } },
      { id: "category-seeding", type: "category", title: "种草建议", action: "种草动作", confidence: "signal", priority: "medium", evidence: [], target: { category: "产品种草", city: "", account_id: "" } },
      { id: "category-campaign", type: "category", title: "营销建议", action: "营销动作", confidence: "validate", priority: "low", evidence: [], target: { category: "营销活动", city: "", account_id: "" } },
      { id: "account-quality", type: "data_quality", title: "账号建议", action: "账号动作", confidence: "validate", priority: "low", evidence: [], target: { category: "", city: "", account_id: "account-store" } },
    ],
    ...overrides,
  };
}

async function loadDashboard() {
  const source = await readFile(dashboardPath, "utf8");
  const window = {};
  const context = vm.createContext({ console, Intl, Map, Number, Object, Set, window });
  vm.runInContext(source, context, { filename: "dealer-dashboard.js" });
  return window.DealerDashboard;
}

async function runDashboardPage(payload) {
  const source = await readFile(dashboardPath, "utf8");
  const elements = Object.fromEntries([
    "data-state",
    "dashboard-content",
    "report-month",
    "freshness-badge",
  ].map((id) => [id, { hidden: id === "dashboard-content", innerHTML: "", textContent: "" }]));
  const document = {
    readyState: "complete",
    getElementById: (id) => elements[id] || null,
    querySelectorAll: () => [],
  };
  const pageCore = {
    ...core,
    destroyCharts: () => {},
    escapeHtml: (value) => String(value ?? ""),
    initIcons: () => false,
    loadData: async () => payload,
    renderError: () => {},
    renderLoading: (target) => { target.innerHTML = "loading"; },
  };
  const window = {
    document,
    history: { replaceState: () => {} },
    InsightCore: pageCore,
    location: { href: "http://localhost/dealer_insight.html" },
  };
  const context = vm.createContext({ console, Date, Intl, Map, Number, Object, Set, URL, window });

  vm.runInContext(source, context, { filename: "dealer-dashboard.js" });
  await new Promise((resolve) => setImmediate(resolve));
  return { dashboard: window.DealerDashboard, elements };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function runScopedDashboard({ href, loadData, windowOverrides = {} }) {
  const source = await readFile(dashboardPath, "utf8");
  const page = await readFile(pagePath, "utf8");
  const elements = {};
  for (const match of page.matchAll(/<[^>]*\sid="([^"]+)"[^>]*>/g)) {
    const tag = match[0];
    const datasetMatch = tag.match(/data-filter-key="([^"]+)"/);
    const listeners = {};
    elements[match[1]] = {
      className: "",
      dataset: datasetMatch ? { filterKey: datasetMatch[1] } : {},
      disabled: /\sdisabled(?:\s|>)/.test(tag),
      hidden: /\shidden(?:\s|>)/.test(tag),
      innerHTML: "",
      textContent: "",
      title: "",
      value: "",
      addEventListener: (type, listener) => { listeners[type] = listener; },
      dispatch: (type) => listeners[type]?.({ target: elements[match[1]] }),
    };
  }
  const filterControls = Object.values(elements).filter((element) => element.dataset.filterKey);
  const document = {
    readyState: "complete",
    getElementById: (id) => elements[id] || null,
    querySelectorAll: (selector) => selector === "[data-filter-key]" || selector === ".filter-control" ? filterControls : [],
  };
  const pageCore = {
    ...core,
    chartTheme: () => ({ colors: {}, grid: {}, ticks: {} }),
    destroyCharts: (charts) => {
      Object.values(charts || {}).forEach((chart) => {
        if (chart && typeof chart.destroy === "function") chart.destroy();
      });
    },
    escapeHtml: (value) => String(value ?? ""),
    initIcons: () => false,
    loadData,
    renderError: (target, error) => { target.innerHTML = `<div role="alert">${error.message}</div>`; },
    renderLoading: (target) => { target.innerHTML = "loading"; },
  };
  const replacedUrls = [];
  const window = {
    document,
    history: { replaceState: (_state, _title, url) => { replacedUrls.push(String(url)); } },
    InsightCore: pageCore,
    location: { href },
    ...windowOverrides,
  };
  const context = vm.createContext({ console, Date, Intl, Map, Number, Object, Set, URL, window });

  vm.runInContext(source, context, { filename: "dealer-dashboard.js" });
  await new Promise((resolve) => setImmediate(resolve));
  return { elements, replacedUrls, window };
}

test("selectDealer returns only the requested dealer and rejects an unknown id", async () => {
  const dashboard = await loadDashboard();
  const dealers = [makeDealer(), makeDealer({ dealer_id: "dealer-b", name: "经销商 B" })];

  assert.equal(dashboard.selectDealer(dealers, "dealer-b").name, "经销商 B");
  assert.equal(dashboard.selectDealer(dealers, "missing"), null);
  assert.equal(dashboard.selectDealer([], "dealer-a"), null);
});

test("selected dealer filter options never include another dealer account", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer();
  const options = dashboard.getFilterOptions(dealer);

  assert.deepEqual([...options.cities], ["上海", "苏州"]);
  assert.deepEqual([...options.accounts].map((item) => item.value), ["account-core", "account-store"]);
  assert.deepEqual([...options.categories], ["产品种草", "营销活动"]);
  assert.deepEqual([...options.formats].map((item) => item.value), ["image", "video"]);
  assert.doesNotMatch(JSON.stringify(options), /B 私密账号/);
});

test("account filtering combines city, account, and cohort without mutating source rows", async () => {
  const dashboard = await loadDashboard();
  const accounts = makeDealer().accounts;
  const original = structuredClone(accounts);

  assert.deepEqual(
    dashboard.filterAccounts(accounts, { city: "苏州", accountId: "account-store", cohort: "expanded_store" }).map((row) => row.author_id),
    ["account-store"],
  );
  assert.deepEqual(dashboard.filterAccounts(accounts, { city: "上海", cohort: "expanded_store" }), []);
  assert.deepEqual(accounts, original);
});

test("category, city, and format filters return only matching generated records", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer();

  assert.deepEqual(dashboard.filterCategories(dealer.content.categories, "营销活动").map((row) => row.category), ["营销活动"]);
  assert.deepEqual(
    dashboard.filterCityCohorts(dealer.content.by_city_cohort, { city: "苏州", cohort: "expanded_store", category: "营销活动" }).map((row) => row.city),
    ["苏州"],
  );
  assert.deepEqual([...dashboard.buildFormatViewModel(dealer.content, "video", core)].map((row) => row.key), ["video"]);
  assert.equal(dashboard.buildFormatViewModel(dealer.content, "video", core)[0].share, "P:0.4");
});

test("one content scope drives city category and city format values without dealer-total fallback", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer();

  const categoryScope = dashboard.buildContentScope(dealer, { city: "上海", category: "产品种草" }, core);
  assert.equal(categoryScope.available, true);
  assert.equal(categoryScope.level, "city");
  assert.equal(categoryScope.dimension, "category");
  assert.equal(categoryScope.values.notes, 6);
  assert.equal(categoryScope.values.reads, 900);
  assert.deepEqual([...categoryScope.categories].map((item) => item.category), ["产品种草"]);
  assert.equal(categoryScope.formatsAvailable, false);
  assert.equal(categoryScope.formats.length, 0);

  const formatScope = dashboard.buildContentScope(dealer, { city: "上海", format: "image" }, core);
  assert.equal(formatScope.available, true);
  assert.equal(formatScope.level, "city");
  assert.equal(formatScope.dimension, "format");
  assert.equal(formatScope.values.notes, 2);
  assert.equal(formatScope.values.note_share, 1 / 3);
  assert.deepEqual([...formatScope.formats].map((item) => item.key), ["image"]);
  assert.equal(formatScope.categoriesAvailable, false);
  assert.equal(formatScope.categories.length, 0);
});

test("account content scope never falls back to dealer category or format totals", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer();

  const accountScope = dashboard.buildContentScope(dealer, { accountId: "account-core" }, core);
  assert.equal(accountScope.available, true);
  assert.equal(accountScope.level, "account");
  assert.equal(accountScope.values.reads, 900);
  assert.equal(accountScope.categoriesAvailable, false);
  assert.equal(accountScope.formatsAvailable, false);
  assert.equal(accountScope.categories.length, 0);
  assert.equal(accountScope.formats.length, 0);

  const unsupported = dashboard.buildContentScope(dealer, { accountId: "account-core", category: "产品种草" }, core);
  assert.equal(unsupported.available, false);
  assert.equal(unsupported.reason, "account_content_breakdown_unavailable");
  assert.equal(unsupported.values, null);
  assert.equal(unsupported.categories.length, 0);
  assert.equal(unsupported.formats.length, 0);
});

test("real JSON city content supports city plus category and city plus format scopes", async () => {
  const dashboard = await loadDashboard();
  const data = JSON.parse(await readFile(insightDataPath, "utf8"));
  const dealer = data.dealers.find((item) => item.content.by_city_cohort.some((row) => row.content.notes > 0 && row.content.categories.length > 0));
  const cityRow = dealer.content.by_city_cohort.find((row) => row.content.notes > 0 && row.content.categories.length > 0);
  const cityRows = dealer.content.by_city_cohort.filter((row) => row.city === cityRow.city);
  const category = cityRow.content.categories[0].category;
  const expectedCategoryNotes = cityRows.reduce((total, row) => total + row.content.categories.filter((item) => item.category === category).reduce((sum, item) => sum + item.notes, 0), 0);
  const expectedImageNotes = cityRows.reduce((total, row) => total + row.content.image_notes, 0);
  const expectedCityNotes = cityRows.reduce((total, row) => total + row.content.notes, 0);

  const categoryScope = dashboard.buildContentScope(dealer, { city: cityRow.city, category }, core);
  const formatScope = dashboard.buildContentScope(dealer, { city: cityRow.city, format: "image" }, core);

  assert.equal(categoryScope.values.notes, expectedCategoryNotes);
  assert.equal(formatScope.values.notes, expectedImageNotes);
  assert.equal(formatScope.values.note_share, expectedImageNotes / expectedCityNotes);
  assert.equal(categoryScope.level, "city");
  assert.equal(formatScope.level, "city");
});

test("core KPI view model formats actual, target, completion, pacing, and status from data", async () => {
  const dashboard = await loadDashboard();
  const cards = dashboard.buildKpiViewModel(makeDealer(), core);

  assert.equal(cards.length, 3);
  assert.deepEqual(
    { actual: cards[0].actual, target: cards[0].target, completion: cards[0].completion, pacingGap: cards[0].pacingGap, elapsed: cards[0].elapsed, status: cards[0].status },
    { actual: "N:900", target: "N:1800", completion: "P:0.5", pacingGap: "S:0.167", elapsed: "P:0.333", status: "leading" },
  );
});

test("expanded-store view model has observations but never manufactures FY26 targets", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer({
    cohort: "expanded_store",
    kpi: {
      reads: { actual: 0, target: 0, completion_rate: null, pacing_gap: null, status: "unmatched" },
      interactions: { actual: 0, target: 0, completion_rate: null, pacing_gap: null, status: "unmatched" },
      fans: { actual: 0, target: 0, completion_rate: null, pacing_gap: null, status: "unmatched" },
      elapsed_ratio: 0.333,
      account_statuses: [],
      overall_status: "unmatched",
    },
  });

  assert.equal(dashboard.buildKpiViewModel(dealer, core).length, 0);
  const expanded = dashboard.buildExpandedStoreViewModel(dealer, core);
  assert.equal(expanded[0].value, "N:300");
  assert.equal(expanded.every((metric) => !("target" in metric) && !("completion" in metric)), true);
});

test("expanded-store renderer clears stale content before hiding an empty section", async () => {
  const dashboard = await loadDashboard();
  const section = { hidden: true };
  const root = { innerHTML: "" };

  dashboard.renderExpandedStore(section, root, [{ label: "阅读量", value: "N:300" }], core);
  assert.equal(section.hidden, false);
  assert.match(root.innerHTML, /N:300/);

  dashboard.renderExpandedStore(section, root, [], core);
  assert.equal(section.hidden, true);
  assert.equal(root.innerHTML, "");
});

test("recommendation filters keep dealer-wide actions and only matching targets", async () => {
  const dashboard = await loadDashboard();
  const recommendations = makeDealer().recommendations;

  assert.deepEqual(
    dashboard.filterRecommendations(recommendations, { category: "产品种草", accountId: "" }).map((item) => item.id),
    ["general", "category-seeding"],
  );
  assert.deepEqual(
    dashboard.filterRecommendations(recommendations, { category: "", accountId: "account-store" }).map((item) => item.id),
    ["general", "account-quality"],
  );
});

test("evidence formatting uses explicit metric formats and preserves evidence scope", async () => {
  const dashboard = await loadDashboard();

  assert.equal(dashboard.formatEvidenceValue("reads_pacing_gap", -0.086, core), "S:-0.086");
  assert.equal(dashboard.formatEvidenceValue("reads_completion", 0.247, core), "P:0.247");
  assert.equal(dashboard.formatEvidenceValue("reads_actual", 597001, core), "N:597001");

  const evidence = dashboard.buildEvidenceViewModel({
    metric: "reads_pacing_gap",
    value: -0.086,
    benchmark: 0,
    scope: "q4_time_progress",
  }, core);
  assert.equal(evidence.value, "S:-0.086");
  assert.equal(evidence.benchmark, "S:0");
  assert.equal(evidence.scope, "q4_time_progress");
  assert.equal(evidence.scopeLabel, "Q4 时间进度");

  const html = dashboard.renderEvidenceItem({
    metric: "reads_pacing_gap",
    value: -0.086,
    benchmark: 0,
    scope: "q4_time_progress",
  }, core, (value) => String(value));
  assert.match(html, /S:-0\.086/);
  assert.match(html, /Q4 时间进度/);
});

test("account table view model exposes accessible confidence labels", async () => {
  const dashboard = await loadDashboard();
  const dealer = makeDealer();
  dealer.accounts.push({
    author_id: "account-unknown",
    account_name: "A 待补充账号",
    store: "",
    cohort: "expanded_store",
    city: "",
    confidence: "unknown",
    metrics: {},
  });

  const rows = dashboard.buildAccountTableViewModel(dealer, dealer.accounts, core);
  assert.equal(rows.find((row) => row.authorId === "account-store").confidenceLabel, "推断归属");
  assert.equal(rows.find((row) => row.authorId === "account-unknown").confidenceLabel, "归属待补充");
});

test("complete view model contains selected dealer details but no unselected dealer accounts", async () => {
  const dashboard = await loadDashboard();
  const selected = makeDealer();
  const other = makeDealer({
    dealer_id: "dealer-b",
    name: "经销商 B",
    accounts: [{ author_id: "secret", account_name: "B 私密账号", cohort: "core_kpi", city: "北京", metrics: {} }],
  });
  const data = {
    source_month: "2026-07",
    generated_at: "2026-08-06T12:00:00Z",
    dealers: [selected, other],
    quality: {
      unmatched_accounts: [{ author_id: "secret", account_name: "B 私密账号" }],
    },
  };
  const viewModel = dashboard.buildDealerViewModel(data, { dealerId: "dealer-a", city: "", accountId: "", format: "", category: "", cohort: "" }, core);
  const serialized = JSON.stringify(viewModel);

  assert.equal(viewModel.dealer.dealer_id, "dealer-a");
  assert.match(serialized, /A 核心账号/);
  assert.doesNotMatch(serialized, /B 私密账号|"secret"/);
});

test("empty inputs produce stable empty view models", async () => {
  const dashboard = await loadDashboard();

  assert.equal(JSON.stringify(dashboard.getFilterOptions(null)), JSON.stringify({ cities: [], accounts: [], categories: [], formats: [] }));
  assert.equal(dashboard.filterAccounts(null, {}).length, 0);
  assert.equal(dashboard.filterRecommendations(null, {}).length, 0);
  assert.equal(dashboard.buildDealerViewModel({ dealers: [] }, { dealerId: "missing" }, core), null);
});

test("empty dealers response reveals a visible dashboard empty state", async () => {
  const { elements } = await runDashboardPage({
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: "2026-08-06T12:00:00Z",
    dealers: [],
  });

  assert.equal(elements["dashboard-content"].hidden, false);
  assert.match(elements["dashboard-content"].innerHTML, /没有可显示的经销商数据/);
});

test("Dealer page loads index then dealer_id scoped artifact and never requests shared insight data", async () => {
  const dealerA = makeDealer();
  const dealerB = makeDealer({ dealer_id: "dealer-b", name: "经销商 B" });
  const index = {
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: "2026-08-08T12:00:00Z",
    data_freshness: { source_snapshot_at: "2026-08-01", basis: "note_export_timestamp", is_fallback: false },
    quality: { quality_status: "ready", errors: [] },
    dealers: [
      { dealer_id: dealerA.dealer_id, name: dealerA.name },
      { dealer_id: dealerB.dealer_id, name: dealerB.name },
    ],
  };
  const requests = [];
  const responses = {
    "generated/dealer_index.json": index,
    "generated/dealers/dealer-b.json": { ...index, dealers: undefined, dealer: dealerB },
  };
  const { elements } = await runScopedDashboard({
    href: "http://localhost/dealer_insight.html?dealer_id=dealer-b",
    loadData: async (url) => {
      requests.push(url);
      if (!responses[url]) throw new Error(`unexpected URL: ${url}`);
      return responses[url];
    },
  });
  await new Promise((resolve) => setImmediate(resolve));

  assert.deepEqual(requests, ["generated/dealer_index.json", "generated/dealers/dealer-b.json"]);
  assert.equal(requests.some((url) => String(url).includes("insight_data.json")), false);
  assert.equal(elements["dealer-name"].textContent, "经销商 B");
});

test("newer Dealer selection wins when an older scoped request resolves last", async () => {
  const dealerA = makeDealer();
  const dealerB = makeDealer({ dealer_id: "dealer-b", name: "经销商 B" });
  const index = {
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: "2026-08-08T12:00:00Z",
    data_freshness: { source_snapshot_at: "2026-08-01", basis: "note_export_timestamp", is_fallback: false },
    quality: { quality_status: "ready", errors: [] },
    dealers: [
      { dealer_id: dealerA.dealer_id, name: dealerA.name },
      { dealer_id: dealerB.dealer_id, name: dealerB.name },
    ],
  };
  const pendingA = deferred();
  const pendingB = deferred();
  const requests = [];
  const { elements } = await runScopedDashboard({
    href: "http://localhost/dealer_insight.html?dealer_id=dealer-a",
    loadData: async (url) => {
      requests.push(url);
      if (url === "generated/dealer_index.json") return index;
      if (url === "generated/dealers/dealer-a.json") return pendingA.promise;
      if (url === "generated/dealers/dealer-b.json") return pendingB.promise;
      throw new Error(`unexpected URL: ${url}`);
    },
  });

  const dealerSelect = elements["dealer-filter"];
  dealerSelect.value = "dealer-b";
  dealerSelect.dispatch("change");
  pendingB.resolve({ ...index, dealers: undefined, dealer: dealerB });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["dealer-name"].textContent, "经销商 B");

  pendingA.resolve({ ...index, dealers: undefined, dealer: dealerA });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(elements["dealer-name"].textContent, "经销商 B");
  assert.deepEqual(requests, [
    "generated/dealer_index.json",
    "generated/dealers/dealer-a.json",
    "generated/dealers/dealer-b.json",
  ]);
});

test("Dealer Chart constructor failure destroys partial charts and preserves data with all fallbacks", async () => {
  const dealer = makeDealer();
  const index = {
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: "2026-08-08T12:00:00Z",
    data_freshness: { source_snapshot_at: "2026-08-01", basis: "note_export_timestamp", is_fallback: false },
    quality: { quality_status: "ready", errors: [] },
    dealers: [{ dealer_id: dealer.dealer_id, name: dealer.name }],
  };
  const chartState = { calls: 0, destroyed: 0 };
  function ThrowingChart() {
    chartState.calls += 1;
    if (chartState.calls === 2) throw new Error("fixture chart constructor failed");
    return { destroy: () => { chartState.destroyed += 1; } };
  }
  const { elements } = await runScopedDashboard({
    href: "http://localhost/dealer_insight.html?dealer_id=dealer-a",
    loadData: async (url) => url === "generated/dealer_index.json"
      ? index
      : { ...index, dealers: undefined, dealer },
    windowOverrides: { Chart: ThrowingChart },
  });
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(chartState.calls, 2);
  assert.equal(chartState.destroyed, 1);
  assert.equal(elements["dashboard-content"].hidden, false);
  assert.equal(elements["category-chart-fallback"].hidden, false);
  assert.equal(elements["format-chart-fallback"].hidden, false);
  assert.match(elements["kpi-cards"].innerHTML, /阅读量/);
  assert.match(elements["account-table"].innerHTML, /A 核心账号/);
  assert.match(elements["action-list"].innerHTML, /经销商级建议/);
  assert.equal(elements["data-state"].innerHTML, "");
});

test("Dealer page labels scoped source freshness instead of artifact build time", async () => {
  const dealer = makeDealer();
  const sourceSnapshot = "2026-08-01T00:00:00Z";
  const generatedAt = "2026-08-08T12:00:00Z";
  const index = {
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: generatedAt,
    data_freshness: { source_snapshot_at: sourceSnapshot, basis: "note_export_timestamp", is_fallback: false },
    quality: { quality_status: "ready", errors: [] },
    dealers: [{ dealer_id: dealer.dealer_id, name: dealer.name }],
  };
  const { elements, window } = await runScopedDashboard({
    href: "http://localhost/dealer_insight.html?dealer_id=dealer-a",
    loadData: async (url) => url === "generated/dealer_index.json" ? index : { ...index, dealers: undefined, dealer },
  });
  await new Promise((resolve) => setImmediate(resolve));
  const formatter = new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

  assert.equal(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(sourceSnapshot))}`);
  assert.notEqual(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(generatedAt))}`);
  assert.equal(window.DealerDashboard.buildDealerViewModel(
    { ...index, dealer_options: index.dealers, dealer },
    { dealerId: dealer.dealer_id },
    core,
  ).dataFreshness.source_snapshot_at, sourceSnapshot);
});
