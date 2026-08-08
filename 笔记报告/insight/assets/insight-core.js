(function (global) {
  "use strict";

  const EMPTY_VALUE = "—";
  const FONT_FAMILY = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif";
  const STATUS_LABELS = Object.freeze({
    leading: "领先",
    normal: "正常",
    warning: "预警",
    critical: "严重落后",
    unmatched: "目标未关联",
  });

  function isNumber(value) {
    return value !== null && value !== "" && Number.isFinite(Number(value));
  }

  async function loadData(url = "generated/insight_data.json") {
    let response;

    try {
      response = await global.fetch(url);
    } catch (error) {
      throw new Error(`数据加载失败，请检查网络或本地服务。${error && error.message ? ` ${error.message}` : ""}`);
    }

    if (!response || !response.ok) {
      const status = response && response.status ? `（HTTP ${response.status}）` : "";
      throw new Error(`数据加载失败${status}，请确认数据文件可访问。`);
    }

    let data;
    try {
      data = await response.json();
    } catch (error) {
      throw new Error("数据文件不是有效的 JSON，请重新生成数据。", { cause: error });
    }

    if (!data || data.schema_version !== "1.0") {
      throw new Error("数据版本不受支持，需要 schema_version 1.0。");
    }

    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(data.source_month || "")) {
      throw new Error("数据月份无效，需要 YYYY-MM 格式的 source_month。");
    }

    const quality = data.quality || {};
    if (quality.quality_status === "failed" || (Array.isArray(quality.errors) && quality.errors.length > 0)) {
      throw new Error("数据质量检查失败，请重新生成并核对数据。");
    }

    return data;
  }

  function formatNumber(value, options = {}) {
    if (!isNumber(value)) {
      return EMPTY_VALUE;
    }

    return new Intl.NumberFormat("zh-CN", options).format(Number(value));
  }

  function formatPercent(value, digits = 1) {
    if (!isNumber(value)) {
      return EMPTY_VALUE;
    }

    return new Intl.NumberFormat("zh-CN", {
      style: "percent",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(Number(value));
  }

  function formatSignedPoints(value, digits = 1) {
    if (!isNumber(value)) {
      return EMPTY_VALUE;
    }

    const points = Number(value) * 100;
    const sign = points > 0 ? "+" : "";
    return `${sign}${points.toFixed(digits)}pp`;
  }

  function statusLabel(status) {
    return STATUS_LABELS[status] || "未知状态";
  }

  function statusClass(status) {
    return Object.prototype.hasOwnProperty.call(STATUS_LABELS, status)
      ? `status--${status}`
      : "status--unknown";
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderMetricCard(config = {}) {
    const context = Array.isArray(config.context) ? config.context : [];
    const contextRows = context.map((row) => `
      <div class="metric-card__context-row">
        <span>${escapeHtml(row && row.label)}</span>
        <strong>${escapeHtml(row && row.value)}</strong>
      </div>`).join("");
    const status = config.status
      ? `<span class="status-badge ${statusClass(config.status)}">${escapeHtml(statusLabel(config.status))}</span>`
      : "";

    return `<article class="metric-card">
      <div class="metric-card__header">
        <h3 class="metric-card__label">${escapeHtml(config.label)}</h3>
        ${status}
      </div>
      <p class="metric-card__value">${escapeHtml(config.value == null ? EMPTY_VALUE : config.value)}</p>
      <div class="metric-card__context">${contextRows}</div>
    </article>`;
  }

  function renderLoading(target) {
    if (!target) {
      return;
    }

    target.innerHTML = `<div class="state-panel state-panel--loading" role="status" aria-live="polite">
      <span class="loading-skeleton" aria-hidden="true"></span>
      <span>正在加载数据</span>
    </div>`;
  }

  function renderError(target, error) {
    if (!target) {
      return;
    }

    const message = error && error.message ? error.message : "发生未知错误，请稍后重试。";
    target.innerHTML = `<div class="state-panel state-panel--error" role="alert">
      <strong>暂时无法显示数据</strong>
      <span>${escapeHtml(message)}</span>
    </div>`;
  }

  function chartTheme() {
    return {
      colors: {
        ink: "#1d1d1f",
        muted: "#6e6e73",
        positive: "#30b85a",
        warning: "#e59a16",
        critical: "#d94141",
        info: "#3478f6",
        line: "#dfe3e6",
        surface: "#ffffff",
      },
      font: {
        family: FONT_FAMILY,
        size: 12,
      },
      grid: {
        color: "#e8ebed",
        drawBorder: false,
      },
      ticks: {
        color: "#6e6e73",
        font: { family: FONT_FAMILY, size: 11 },
      },
    };
  }

  function destroyCharts(chartMap) {
    if (!chartMap) {
      return;
    }

    const charts = chartMap instanceof Map ? chartMap.values() : Object.values(chartMap);
    for (const chart of charts) {
      if (!chart || typeof chart.destroy !== "function") {
        continue;
      }
      try {
        chart.destroy();
      } catch (_error) {
        // A stale chart must not block cleanup of remaining instances.
      }
    }
  }

  function initIcons() {
    if (!global.lucide || typeof global.lucide.createIcons !== "function") {
      return false;
    }

    global.lucide.createIcons();
    return true;
  }

  global.InsightCore = Object.freeze({
    loadData,
    formatNumber,
    formatPercent,
    formatSignedPoints,
    statusLabel,
    statusClass,
    escapeHtml,
    renderMetricCard,
    renderLoading,
    renderError,
    chartTheme,
    destroyCharts,
    initIcons,
  });
})(window);
