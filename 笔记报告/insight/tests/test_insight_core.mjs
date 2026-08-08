import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const corePath = new URL("../assets/insight-core.js", import.meta.url);
const indexPath = new URL("../index.html", import.meta.url);

async function loadCore(windowOverrides = {}) {
  const source = await readFile(corePath, "utf8");
  const window = { ...windowOverrides };
  const context = vm.createContext({
    console,
    Intl,
    Map,
    Object,
    window,
  });

  vm.runInContext(source, context, { filename: "insight-core.js" });
  return window.InsightCore;
}

async function runEntryPage(payload) {
  const source = await readFile(indexPath, "utf8");
  const inlineScripts = [...source.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
    .map((match) => match[1])
    .filter((script) => script.trim());
  const elements = Object.fromEntries([
    "data-root",
    "report-month",
    "scope-month",
    "freshness-badge",
    "quality-badge",
  ].map((id) => [id, { className: "", innerHTML: "", textContent: "" }]));
  const core = {
    formatNumber: (value) => String(value),
    formatPercent: (value) => String(value),
    initIcons: () => false,
    loadData: async () => payload,
    renderError: () => {},
    renderLoading: () => {},
    renderMetricCard: ({ label }) => `<article>${label}</article>`,
  };
  const window = { InsightCore: core };
  const context = vm.createContext({
    console,
    Date,
    document: { getElementById: (id) => elements[id] },
    Intl,
    Number,
    window,
  });

  vm.runInContext(inlineScripts.at(-1), context, { filename: "index.html:inline-script" });
  await new Promise((resolve) => setImmediate(resolve));
  return elements;
}

test("formatNumber handles missing, zero, large, and decimal values", async () => {
  const core = await loadCore();

  assert.equal(core.formatNumber(null), "—");
  assert.equal(core.formatNumber(0), "0");
  assert.equal(core.formatNumber(1234567), "1,234,567");
  assert.equal(core.formatNumber(1234.56, { maximumFractionDigits: 1 }), "1,234.6");
  assert.equal(core.formatNumber(Number.POSITIVE_INFINITY), "—");
});

test("formatPercent treats input as a ratio and preserves zero", async () => {
  const core = await loadCore();

  assert.equal(core.formatPercent(null), "—");
  assert.equal(core.formatPercent(0), "0.0%");
  assert.equal(core.formatPercent(0.1234), "12.3%");
  assert.equal(core.formatPercent(12.3456, 2), "1,234.56%");
});

test("formatSignedPoints formats ratio differences as signed percentage points", async () => {
  const core = await loadCore();

  assert.equal(core.formatSignedPoints(null), "—");
  assert.equal(core.formatSignedPoints(0), "0.0pp");
  assert.equal(core.formatSignedPoints(0.064), "+6.4pp");
  assert.equal(core.formatSignedPoints(-0.152, 1), "-15.2pp");
});

test("status mappings cover operating states and unknown values", async () => {
  const core = await loadCore();
  const expected = {
    leading: ["领先", "status--leading"],
    normal: ["正常", "status--normal"],
    warning: ["预警", "status--warning"],
    critical: ["严重落后", "status--critical"],
    unmatched: ["目标未关联", "status--unmatched"],
    unexpected: ["未知状态", "status--unknown"],
  };

  for (const [status, [label, className]] of Object.entries(expected)) {
    assert.equal(core.statusLabel(status), label);
    assert.equal(core.statusClass(status), className);
  }
});

test("escapeHtml escapes tags, ampersands, and both quote types", async () => {
  const core = await loadCore();

  assert.equal(
    core.escapeHtml(`<script data-x="a&b">'unsafe'</script>`),
    "&lt;script data-x=&quot;a&amp;b&quot;&gt;&#39;unsafe&#39;&lt;/script&gt;",
  );
});

test("renderMetricCard renders only supplied display values and escapes text", async () => {
  const core = await loadCore();
  const html = core.renderMetricCard({
    label: "自定义 <指标>",
    value: "98,765",
    status: "leading",
    context: [
      { label: "目标", value: "120,000" },
      { label: "节奏", value: "+3.2pp" },
    ],
  });

  assert.match(html, /自定义 &lt;指标&gt;/);
  assert.match(html, /98,765/);
  assert.match(html, /120,000/);
  assert.match(html, /\+3\.2pp/);
  assert.match(html, /status--leading/);
  assert.doesNotMatch(html, /2026-07|48236|推荐|建议/);
});

test("renderLoading and renderError replace target content with accessible states", async () => {
  const core = await loadCore();
  const target = { innerHTML: "stale" };

  core.renderLoading(target);
  assert.match(target.innerHTML, /role="status"/);
  assert.match(target.innerHTML, /正在加载数据/);

  core.renderError(target, new Error(`<加载失败 & 重试>`));
  assert.match(target.innerHTML, /role="alert"/);
  assert.match(target.innerHTML, /&lt;加载失败 &amp; 重试&gt;/);
  assert.doesNotMatch(target.innerHTML, /<加载失败/);
});

test("entry page renders generator failed quality as critical and unavailable", async () => {
  const elements = await runEntryPage({
    schema_version: "1.0",
    source_month: "2026-08",
    generated_at: "2026-08-06T12:00:00Z",
    quality: {
      quality_status: "failed",
      errors: [],
      warnings: [],
      account_cohorts: {},
      category_completeness: {},
      city_identification: {},
    },
  });

  assert.equal(elements["quality-badge"].textContent, "数据不可用");
  assert.match(elements["quality-badge"].className, /status--critical/);
});

test("entry page labels source snapshot freshness instead of build time", async () => {
  const sourceSnapshot = "2026-08-01T00:00:00Z";
  const generatedAt = "2026-08-08T12:00:00Z";
  const elements = await runEntryPage({
    schema_version: "1.0",
    source_month: "2026-07",
    generated_at: generatedAt,
    metadata: {
      data_freshness: {
        source_snapshot_at: sourceSnapshot,
        basis: "note_export_timestamp",
        is_fallback: false,
      },
    },
    quality: { quality_status: "ready", errors: [], warnings: [], account_cohorts: {}, category_completeness: {}, city_identification: {} },
  });
  const formatter = new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

  assert.equal(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(sourceSnapshot))}`);
  assert.notEqual(elements["freshness-badge"].textContent, `更新于 ${formatter.format(new Date(generatedAt))}`);
});

test("loadData accepts valid data and uses the default URL", async () => {
  let requestedUrl;
  const payload = { schema_version: "1.0", source_month: "2026-08" };
  const core = await loadCore({
    fetch: async (url) => {
      requestedUrl = url;
      return { ok: true, json: async () => payload };
    },
  });

  assert.equal(await core.loadData(), payload);
  assert.equal(requestedUrl, "generated/insight_data.json");
});

test("loadData rejects unsupported schemas with a localized error", async () => {
  const core = await loadCore({
    fetch: async () => ({
      ok: true,
      json: async () => ({ schema_version: "2.0", source_month: "2026-08" }),
    }),
  });

  await assert.rejects(core.loadData(), /数据版本不受支持.*1\.0/);
});

test("loadData rejects invalid source months and unsuccessful responses", async () => {
  const invalidMonthCore = await loadCore({
    fetch: async () => ({
      ok: true,
      json: async () => ({ schema_version: "1.0", source_month: "2026-13" }),
    }),
  });
  await assert.rejects(invalidMonthCore.loadData(), /数据月份无效/);

  const failedResponseCore = await loadCore({
    fetch: async () => ({ ok: false, status: 404 }),
  });
  await assert.rejects(failedResponseCore.loadData("missing.json"), /数据加载失败.*404/);
});

test("loadData rejects a shared payload with failed quality", async () => {
  const core = await loadCore({
    fetch: async () => ({
      ok: true,
      json: async () => ({
        schema_version: "1.0",
        source_month: "2026-07",
        quality: { quality_status: "failed", errors: [] },
      }),
    }),
  });

  await assert.rejects(core.loadData(), /数据质量检查失败/);
});

test("loadData rejects a dealer-scoped payload with quality errors", async () => {
  const core = await loadCore({
    fetch: async () => ({
      ok: true,
      json: async () => ({
        schema_version: "1.0",
        source_month: "2026-07",
        quality: { quality_status: "ready", errors: ["fixture quality error"] },
        dealer: { dealer_id: "dealer-a", name: "Dealer A" },
      }),
    }),
  });

  await assert.rejects(core.loadData("generated/dealers/dealer-a.json"), /数据质量检查失败/);
});

test("chartTheme returns reusable Chart.js colors and readable defaults", async () => {
  const core = await loadCore();
  const theme = core.chartTheme();

  assert.equal(theme.colors.positive, "#30b85a");
  assert.equal(theme.colors.ink, "#1d1d1f");
  assert.equal(theme.font.family.includes("Microsoft YaHei"), true);
  assert.equal(theme.grid.color, "#e8ebed");
});

test("destroyCharts destroys every chart in objects and maps without stopping on errors", async () => {
  const core = await loadCore();
  const destroyed = [];
  const charts = {
    first: { destroy: () => destroyed.push("first") },
    broken: { destroy: () => { throw new Error("already gone"); } },
    second: { destroy: () => destroyed.push("second") },
    empty: null,
  };

  assert.doesNotThrow(() => core.destroyCharts(charts));
  assert.deepEqual(destroyed, ["first", "second"]);

  const mapDestroyed = [];
  core.destroyCharts(new Map([["chart", { destroy: () => mapDestroyed.push("map") }]]));
  assert.deepEqual(mapDestroyed, ["map"]);
});

test("initIcons calls Lucide only when the browser global is available", async () => {
  let calls = 0;
  const withLucide = await loadCore({
    lucide: { createIcons: () => { calls += 1; } },
  });
  assert.equal(withLucide.initIcons(), true);
  assert.equal(calls, 1);

  const withoutLucide = await loadCore();
  assert.equal(withoutLucide.initIcons(), false);
});
