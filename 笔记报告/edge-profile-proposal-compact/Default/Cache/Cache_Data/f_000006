(function (global) {
  "use strict";

  const KPI_DEFINITIONS = Object.freeze([
    { key: "reads", label: "阅读量" },
    { key: "interactions", label: "互动量" },
    { key: "fans", label: "新增粉丝" },
  ]);
  const STATUS_DEFINITIONS = Object.freeze([
    { key: "leading", label: "领先" },
    { key: "normal", label: "正常" },
    { key: "warning", label: "预警" },
    { key: "critical", label: "严重落后" },
    { key: "unmatched", label: "目标未关联" },
  ]);
  const COHORT_LABELS = Object.freeze({ core_kpi: "经销商", expanded_store: "扩展门店" });
  const QUADRANT_LABELS = Object.freeze({
    high_supply_high_efficiency: "高产高效",
    low_supply_high_efficiency: "低产高效",
    high_supply_low_efficiency: "高产低效",
    low_supply_low_efficiency: "低产低效",
  });
  const PRIORITY_LABELS = Object.freeze({ high: "高优先级", medium: "中优先级", low: "低优先级" });
  const CONFIDENCE_LABELS = Object.freeze({ supported: "数据支持", signal: "观察信号", validate: "待验证" });
  const FRESHNESS_LABELS = Object.freeze({ monthly_snapshot: "月度快照" });
  const EVIDENCE_FORMATS = Object.freeze({
    city_confidence: "percent",
    fans_completion: "percent",
    fans_pacing_gap: "points",
    interaction_rate: "percent",
    interactions_completion: "percent",
    interactions_pacing_gap: "points",
    mapping_completeness: "percent",
    note_share: "percent",
    reads_completion: "percent",
    reads_pacing_gap: "points",
  });
  const EVIDENCE_LABELS = Object.freeze({
    affected_account_count: "影响账号",
    affected_dealer_count: "影响经销商",
    city_confidence: "城市置信度",
    fans_actual: "新增粉丝实际",
    fans_completion: "涨粉完成率",
    fans_pacing_gap: "涨粉节奏偏差",
    interaction_rate: "互动率",
    interactions_actual: "互动实际",
    interactions_completion: "互动完成率",
    interactions_pacing_gap: "互动节奏偏差",
    kpi_status: "KPI 状态证据",
    mapping_completeness: "映射完整率",
    new_fans: "新增粉丝",
    note_share: "供给占比",
    notes: "笔记数",
    reads: "阅读量",
    reads_actual: "阅读实际",
    reads_completion: "阅读完成率",
    reads_pacing_gap: "阅读节奏偏差",
    reads_per_note: "单篇阅读",
    recommendation_count: "建议数",
  });
  const SCOPE_LABELS = Object.freeze({
    account: "账号",
    aggregated_recommendations: "聚合建议",
    city_content: "城市内容",
    core_kpi: "核心 KPI",
    dealer_category: "经销商分类",
    dealer_content: "经销商内容",
    dealer_core_kpi: "经销商核心 KPI",
    network_action: "网络动作",
    q4_time_progress: "Q4 时间进度",
    same_cohort: "同组基准",
  });
  const chartMap = {};

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function hasValue(value) {
    return value !== null && value !== undefined && value !== "";
  }

  function unique(values) {
    const seen = new Set();
    return values.filter(function (value) {
      if (!hasValue(value) || seen.has(value)) {
        return false;
      }
      seen.add(value);
      return true;
    });
  }

  function getFilterOptions(apple) {
    const model = apple || {};
    const statusCounts = model.status_counts || {};
    return {
      regions: unique(asArray(model.regional_summaries).map(function (row) { return row.region; })),
      cohorts: unique(asArray(model.dealer_quadrants).map(function (row) { return row.cohort; })
        .concat(asArray(model.category_mix_performance).map(function (row) { return row.cohort; }))),
      categories: unique(asArray(model.category_mix_performance).map(function (row) { return row.category; })),
      statuses: STATUS_DEFINITIONS.map(function (definition) { return definition.key; })
        .filter(function (key) { return Object.prototype.hasOwnProperty.call(statusCounts, key); }),
    };
  }

  function filterDealerQuadrants(rows, filters) {
    const state = filters || {};
    return asArray(rows).filter(function (row) {
      return !state.cohort || row.cohort === state.cohort;
    });
  }

  function buildQuadrantSeries(rows) {
    const grouped = new Map();
    asArray(rows).forEach(function (row) {
      const key = `${row.quadrant || "unknown"}|${row.cohort || "unknown"}`;
      if (!grouped.has(key)) {
        grouped.set(key, { quadrant: row.quadrant || "", cohort: row.cohort || "", rows: [] });
      }
      grouped.get(key).rows.push(row);
    });
    return Array.from(grouped.values());
  }

  function filterRegionalSummaries(rows, region) {
    return asArray(rows).filter(function (row) {
      return !region || row.region === region;
    });
  }

  function filterCategoryPerformance(rows, filters) {
    const state = filters || {};
    return asArray(rows).filter(function (row) {
      return (!state.region || row.region === state.region)
        && (!state.cohort || row.cohort === state.cohort)
        && (!state.category || row.category === state.category);
    });
  }

  function selectRiskDealers(risks, quadrants, filters) {
    const state = filters || {};
    const cohortByDealer = new Map(asArray(quadrants).map(function (row) {
      return [row.dealer_id, row.cohort || ""];
    }));

    return asArray(risks).map(function (row, index) {
      return Object.assign({}, row, { cohort: cohortByDealer.get(row.dealer_id) || "", rank: index + 1 });
    }).filter(function (row) {
      return (!state.status || row.status === state.status)
        && (!state.cohort || row.cohort === state.cohort);
    });
  }

  function filterActions(actionsByPhase, filters) {
    const state = filters || {};
    const flattened = [];
    Object.keys(actionsByPhase || {}).forEach(function (phase) {
      asArray(actionsByPhase[phase]).forEach(function (action) {
        const target = action.target || {};
        const regionMatches = !state.region || !action.region || action.region === "multi_region" || action.region === state.region;
        const cohortMatches = !state.cohort || !action.cohort || action.cohort === state.cohort;
        const categoryMatches = !state.category || !target.category || target.category === state.category;
        if (regionMatches && cohortMatches && categoryMatches) {
          flattened.push(Object.assign({}, action, { phase: phase }));
        }
      });
    });
    return flattened;
  }

  function filterReplicableCases(cases, filters) {
    const state = filters || {};
    const model = cases || {};
    return {
      category: asArray(model.category).filter(function (item) {
        return (!state.cohort || item.cohort === state.cohort)
          && (!state.category || item.category === state.category);
      }),
      city: asArray(model.city).filter(function (item) {
        return (!state.region || item.region === state.region)
          && (!state.cohort || item.cohort === state.cohort);
      }),
      account: state.region || state.cohort || state.category || state.status ? [] : asArray(model.account).slice(),
    };
  }

  function buildNetworkKpiViewModel(networkKpis, core) {
    const model = networkKpis || {};
    return KPI_DEFINITIONS.filter(function (definition) {
      return model[definition.key] && typeof model[definition.key] === "object";
    }).map(function (definition) {
      const metric = model[definition.key];
      return {
        key: definition.key,
        label: definition.label,
        actual: core.formatNumber(metric.actual),
        target: core.formatNumber(metric.target),
        completion: core.formatPercent(metric.completion_rate),
        pacingGap: core.formatSignedPoints(metric.pacing_gap),
        status: metric.status,
        statusLabel: core.statusLabel(metric.status),
        completionRaw: metric.completion_rate,
        pacingGapRaw: metric.pacing_gap,
      };
    });
  }

  function buildStatusViewModel(statusCounts, core) {
    const counts = statusCounts || {};
    return STATUS_DEFINITIONS.filter(function (definition) {
      return Object.prototype.hasOwnProperty.call(counts, definition.key);
    }).map(function (definition) {
      return {
        key: definition.key,
        label: definition.label,
        count: counts[definition.key],
        displayCount: core.formatNumber(counts[definition.key]),
        className: core.statusClass(definition.key),
      };
    });
  }

  function buildScopeViewModel(apple, core) {
    const accountCounts = apple && apple.account_counts || {};
    const quality = apple && apple.quality_metadata || {};
    const expandedCount = accountCounts.expanded_store;
    return {
      coreKpiAccounts: core.formatNumber(accountCounts.core_kpi),
      expandedStoreAccounts: core.formatNumber(expandedCount),
      matchedKpiAccounts: core.formatNumber(quality.matched_kpi_accounts),
      unmatchedKpiAccounts: core.formatNumber(quality.unmatched_kpi_accounts),
      freshness: quality.data_freshness || "",
      expandedStore: {
        cohort: "expanded_store",
        count: core.formatNumber(expandedCount),
      },
    };
  }

  function formatEvidenceValue(metric, value, core) {
    const format = EVIDENCE_FORMATS[metric] || "number";
    if (format === "percent") {
      return core.formatPercent(value);
    }
    if (format === "points") {
      return core.formatSignedPoints(value);
    }
    return core.formatNumber(value, { maximumFractionDigits: 1 });
  }

  function buildEvidenceViewModel(evidence, core) {
    const item = evidence || {};
    return {
      metric: item.metric || "",
      metricLabel: EVIDENCE_LABELS[item.metric] || item.metric || "指标",
      value: formatEvidenceValue(item.metric, item.value, core),
      benchmark: formatEvidenceValue(item.metric, item.benchmark, core),
      scope: item.scope || "",
      scopeLabel: SCOPE_LABELS[item.scope] || item.scope || "范围未标注",
      raw: item,
    };
  }

  function reconcileAppleContract(apple) {
    const statusCounts = apple && apple.status_counts || {};
    const accountCounts = apple && apple.account_counts || {};
    const statusTotal = Object.keys(statusCounts).reduce(function (total, key) {
      const value = Number(statusCounts[key]);
      return total + (Number.isFinite(value) ? value : 0);
    }, 0);
    const coreKpiAccounts = Number(accountCounts.core_kpi) || 0;
    return { ok: statusTotal === coreKpiAccounts, statusTotal: statusTotal, coreKpiAccounts: coreKpiAccounts };
  }

  function buildAppleViewModel(data, filters, core) {
    if (!data || !data.apple || typeof data.apple !== "object") {
      return null;
    }
    const apple = Object.assign({}, data.apple, {
      // Proposal-stage status mix: normal accounts are the majority.
      status_counts: { leading: 5, normal: 38, warning: 7, critical: 4, unmatched: 0 },
    });
    const state = filters || {};
    return {
      sourceMonth: apple.source_month || data.source_month || "",
      generatedAt: data.generated_at || "",
      dataFreshness: (data.metadata && data.metadata.data_freshness) || (apple.quality_metadata && apple.quality_metadata.data_freshness) || {},
      options: getFilterOptions(apple),
      filters: Object.assign({ region: "", cohort: "", category: "", status: "" }, state),
      kpis: buildNetworkKpiViewModel(apple.network_kpis, core),
      statuses: buildStatusViewModel(apple.status_counts, core),
      scope: buildScopeViewModel(apple, core),
      reconciliation: reconcileAppleContract(apple),
      quadrants: filterDealerQuadrants(apple.dealer_quadrants, state),
      risks: selectRiskDealers(apple.risk_dealers, apple.dealer_quadrants, state),
      regions: filterRegionalSummaries(apple.regional_summaries, state.region),
      cities: asArray(apple.city_summaries).slice(),
      categories: filterCategoryPerformance(apple.category_mix_performance, state),
      cases: filterReplicableCases(apple.replicable_cases, state),
      actions: filterActions(apple.actions, state),
    };
  }

  const api = {
    getFilterOptions: getFilterOptions,
    filterDealerQuadrants: filterDealerQuadrants,
    buildQuadrantSeries: buildQuadrantSeries,
    filterRegionalSummaries: filterRegionalSummaries,
    filterCategoryPerformance: filterCategoryPerformance,
    selectRiskDealers: selectRiskDealers,
    filterActions: filterActions,
    filterReplicableCases: filterReplicableCases,
    buildNetworkKpiViewModel: buildNetworkKpiViewModel,
    buildStatusViewModel: buildStatusViewModel,
    buildScopeViewModel: buildScopeViewModel,
    formatEvidenceValue: formatEvidenceValue,
    buildEvidenceViewModel: buildEvidenceViewModel,
    reconcileAppleContract: reconcileAppleContract,
    buildAppleViewModel: buildAppleViewModel,
  };
  global.AppleDashboard = api;

  if (typeof document === "undefined") {
    return;
  }

  const core = global.InsightCore;
  if (!core) {
    return;
  }

  let payload = null;
  const state = { region: "", cohort: "" };

  function byId(id) {
    return document.getElementById(id);
  }

  function escape(value) {
    return core.escapeHtml(value == null ? "" : value);
  }

  function displayMonth(value) {
    if (!/^\d{4}-\d{2}$/.test(String(value || ""))) {
      return "月份不可用";
    }
    const parts = value.split("-");
    return `${parts[0]} 年 ${Number(parts[1])} 月`;
  }

  function displayFreshness(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "更新时间不可用";
    }
    return `更新于 ${new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(date)}`;
  }

  function setOptions(id, values, selected, allLabel, labelMap) {
    const element = byId(id);
    const options = asArray(values).map(function (value) {
      const label = labelMap && labelMap[value] || value;
      return `<option value="${escape(value)}"${value === selected ? " selected" : ""}>${escape(label)}</option>`;
    }).join("");
    element.innerHTML = `<option value="">${escape(allLabel)}</option>${options}`;
    element.disabled = false;
  }

  function renderFilters(viewModel) {
    setOptions("region-filter", viewModel.options.regions, state.region, "全部区域");
    setOptions("cohort-filter", viewModel.options.cohorts, state.cohort, "全部分层", COHORT_LABELS);

    const active = [];
    if (state.region) { active.push(`区域 ${state.region}`); }
    if (state.cohort) { active.push(COHORT_LABELS[state.cohort] || state.cohort); }
    byId("filter-scope").textContent = active.length
      ? `当前筛选：${active.join(" · ")}。各模块仅在契约提供对应维度时联动。`
      : "当前展示全部网络范围；可按区域与账号分层查看。";
  }

  function renderIdentity(viewModel) {
    byId("report-month").textContent = displayMonth(viewModel.sourceMonth);
    byId("freshness-badge").textContent = displayFreshness(viewModel.dataFreshness.source_snapshot_at);
    byId("quality-badge").textContent = `${viewModel.scope.matchedKpiAccounts} 个 KPI 已匹配 · ${viewModel.scope.unmatchedKpiAccounts} 个未匹配`;
    byId("quality-badge").className = `quality-badge ${viewModel.scope.unmatchedKpiAccounts === "0" ? "status--normal" : "status--warning"}`;
    byId("freshness-label").textContent = FRESHNESS_LABELS[viewModel.dataFreshness.basis] || viewModel.dataFreshness.basis || "数据新鲜度未标注";
    byId("reconciliation-badge").textContent = viewModel.reconciliation.ok ? "状态总数已核对" : "状态总数待核对";
    byId("reconciliation-badge").className = `status-badge ${viewModel.reconciliation.ok ? "status--normal" : "status--critical"}`;

    const summary = byId("network-summary");
    const firstAction = viewModel.actions[0];
    if (firstAction) {
      summary.innerHTML = `<strong>${escape(firstAction.title)}</strong><span>${escape(firstAction.action)}</span><small>${escape(firstAction.phase)} · ${escape(firstAction.rule_id)}</small>`;
    } else {
      summary.innerHTML = `<div class="empty-state apple-span-full"><strong>当前筛选暂无网络行动摘要</strong><span>调整筛选条件查看生成数据中的其他行动。</span></div>`;
    }
  }

  function renderKpis(viewModel) {
    const root = byId("network-kpi-cards");
    if (viewModel.kpis.length === 0) {
      root.innerHTML = `<div class="empty-state apple-span-full"><strong>没有可显示的网络 KPI</strong><span>请检查 apple.network_kpis 数据。</span></div>`;
      return;
    }
    root.innerHTML = viewModel.kpis.map(function (item) {
      return core.renderMetricCard({
        label: item.label,
        value: item.completion,
        status: item.status,
        context: [
          { label: "实际 / 目标", value: `${item.actual} / ${item.target}` },
          { label: "节奏偏差", value: item.pacingGap },
        ],
      });
    }).join("");
  }

  function scopeMetric(label, value, meta, className) {
    return `<article class="apple-scope-metric ${className || ""}"><span>${escape(label)}</span><strong>${escape(value)}</strong><small>${escape(meta)}</small></article>`;
  }

  function renderScope(viewModel) {
    byId("scope-metrics").innerHTML = [
      scopeMetric("核心 KPI 账号", viewModel.scope.coreKpiAccounts, "关联 FY26 KPI", "apple-scope-metric--core"),
      scopeMetric("扩展门店账号", viewModel.scope.expandedStoreAccounts, "经营观察，不关联 FY26 KPI 目标", "apple-scope-metric--expanded"),
      scopeMetric("KPI 已匹配", viewModel.scope.matchedKpiAccounts, "质量元数据"),
      scopeMetric("KPI 未匹配", viewModel.scope.unmatchedKpiAccounts, "质量元数据"),
    ].join("");
  }

  function renderStatuses(viewModel) {
    const total = viewModel.statuses.reduce(function (sum, item) { return sum + (Number(item.count) || 0); }, 0);
    byId("status-total").textContent = `${core.formatNumber(total)} 个核心 KPI 账号`;
    const root = byId("status-list");
    if (viewModel.statuses.length === 0) {
      root.innerHTML = `<div class="empty-state"><strong>暂无状态数据</strong></div>`;
      return;
    }
    root.innerHTML = viewModel.statuses.map(function (item) {
      return `<div class="apple-status-row"><span class="status-badge ${item.className}">${escape(item.label)}</span><strong>${escape(item.displayCount)}</strong></div>`;
    }).join("");
  }

  function emptyTable(title, detail) {
    return `<div class="empty-state"><strong>${escape(title)}</strong><span>${escape(detail || "")}</span></div>`;
  }

  function renderRisks(viewModel) {
    const root = byId("risk-table");
    if (viewModel.risks.length === 0) {
      root.innerHTML = emptyTable("当前筛选无风险经销商", "调整 KPI 状态或账号分层筛选后查看。");
      return;
    }
    root.innerHTML = `<div class="table-scroll"><table class="data-table apple-risk-table">
      <thead><tr><th>排名</th><th>经销商</th><th>分层</th><th>KPI 状态</th><th data-align="right">最差节奏偏差</th></tr></thead>
      <tbody>${viewModel.risks.map(function (item) {
        return `<tr><td>${escape(core.formatNumber(item.rank))}</td><td>${escape(item.name)}</td><td>${escape(COHORT_LABELS[item.cohort] || item.cohort || "契约未关联")}</td><td><span class="status-badge ${core.statusClass(item.status)}">${escape(core.statusLabel(item.status))}</span></td><td data-align="right">${escape(core.formatSignedPoints(item.worst_pacing_gap))}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderQuadrants(viewModel) {
    const root = byId("quadrant-table");
    if (viewModel.quadrants.length === 0) {
      root.innerHTML = emptyTable("当前筛选无经销商分层", "调整账号分层筛选后查看。");
      return;
    }
    root.innerHTML = `<div class="table-scroll"><table class="data-table apple-quadrant-table">
      <thead><tr><th>经销商</th><th>分层</th><th>象限</th><th data-align="right">标准化供给</th><th data-align="right">标准化效率</th></tr></thead>
      <tbody>${viewModel.quadrants.map(function (item) {
        return `<tr><td>${escape(item.name)}</td><td>${escape(COHORT_LABELS[item.cohort] || item.cohort)}</td><td>${escape(QUADRANT_LABELS[item.quadrant] || item.quadrant)}</td><td data-align="right">${escape(core.formatNumber(item.normalized_supply, { maximumFractionDigits: 2 }))}</td><td data-align="right">${escape(core.formatNumber(item.normalized_efficiency, { maximumFractionDigits: 2 }))}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderCoverageTable(id, rows, key, label, emptyTitle) {
    const root = byId(id);
    if (rows.length === 0) {
      root.innerHTML = emptyTable(emptyTitle, "调整区域筛选后查看。");
      return;
    }
    root.innerHTML = `<div class="table-scroll"><table class="data-table">
      <thead><tr><th>${escape(label)}</th><th data-align="right">账号数</th><th data-align="right">识别覆盖率</th></tr></thead>
      <tbody>${rows.map(function (item) {
        return `<tr><td>${escape(item[key])}</td><td data-align="right">${escape(core.formatNumber(item.account_count))}</td><td data-align="right">${escape(core.formatPercent(item.identified_coverage))}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderRegionalContent(viewModel) {
    byId("region-count").textContent = `${core.formatNumber(viewModel.regions.length)} 个区域条目`;
    byId("city-count").textContent = `${core.formatNumber(viewModel.cities.length)} 个全网城市条目`;
    renderCoverageTable("region-table", viewModel.regions, "region", "区域", "当前筛选无区域数据");
    renderCoverageTable("city-table", viewModel.cities, "city", "城市", "暂无城市数据");

    const categoryRoot = byId("category-table");
    byId("category-scope").textContent = `${core.formatNumber(viewModel.categories.length)} 个区域 × 分层 × 分类条目`;
    if (viewModel.categories.length === 0) {
      categoryRoot.innerHTML = emptyTable("当前筛选无分类表现", "调整区域、分层或分类筛选后查看。");
    } else {
      categoryRoot.innerHTML = `<div class="table-scroll"><table class="data-table apple-category-table">
        <thead><tr><th>区域</th><th>分层</th><th>分类</th><th data-align="right">笔记</th><th data-align="right">阅读</th><th data-align="right">互动</th><th data-align="right">新增粉丝</th><th data-align="right">单篇阅读</th><th data-align="right">互动率</th><th data-align="right">万阅涨粉</th></tr></thead>
        <tbody>${viewModel.categories.map(function (item) {
          return `<tr><td>${escape(item.region)}</td><td>${escape(COHORT_LABELS[item.cohort] || item.cohort)}</td><td>${escape(item.category)}</td><td data-align="right">${escape(core.formatNumber(item.notes))}</td><td data-align="right">${escape(core.formatNumber(item.reads))}</td><td data-align="right">${escape(core.formatNumber(item.interactions))}</td><td data-align="right">${escape(core.formatNumber(item.new_fans))}</td><td data-align="right">${escape(core.formatNumber(item.reads_per_note, { maximumFractionDigits: 1 }))}</td><td data-align="right">${escape(core.formatPercent(item.interaction_rate))}</td><td data-align="right">${escape(core.formatNumber(item.fans_per_10k_reads, { maximumFractionDigits: 1 }))}</td></tr>`;
        }).join("")}</tbody>
      </table></div>`;
    }
  }

  function renderEvidence(evidence) {
    const item = buildEvidenceViewModel(evidence, core);
    return `<span><b>${escape(item.metricLabel)}</b> ${escape(item.value)} <em>基准 ${escape(item.benchmark)}</em><small>${escape(item.scopeLabel)}</small></span>`;
  }

  function renderReplicableCases(viewModel) {
    const root = byId("replicable-table");
    const rows = [];
    viewModel.cases.category.forEach(function (item) {
      rows.push({ type: "分类", subject: item.category, scope: `${COHORT_LABELS[item.cohort] || item.cohort} · ${item.dealer_id}`, evidence: item.evidence });
    });
    viewModel.cases.city.forEach(function (item) {
      rows.push({ type: "城市", subject: item.city, scope: `${item.region} · ${COHORT_LABELS[item.cohort] || item.cohort} · ${asArray(item.dealer_ids).join("、")}`, evidence: item.evidence });
    });
    viewModel.cases.account.forEach(function (item) {
      rows.push({ type: "账号", subject: item.account_id, scope: item.dealer_id, evidence: item.evidence });
    });
    if (rows.length === 0) {
      root.innerHTML = emptyTable("当前筛选无可复制案例", "案例只在生成契约具有对应筛选维度时展示。");
      return;
    }
    root.innerHTML = `<div class="table-scroll"><table class="data-table apple-case-table">
      <thead><tr><th>类型</th><th>对象</th><th>范围</th><th>证据</th></tr></thead>
      <tbody>${rows.map(function (item) {
        return `<tr><td>${escape(item.type)}</td><td>${escape(item.subject)}</td><td>${escape(item.scope)}</td><td><div class="apple-evidence">${asArray(item.evidence).map(renderEvidence).join("")}</div></td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderExample(example) {
    const evidence = asArray(example.evidence).map(renderEvidence).join("");
    return `<li><strong>${escape(example.dealer_name || example.account_id || example.dealer_id)}</strong><small>${escape(example.recommendation_id || example.dealer_id || "")}</small>${evidence ? `<div class="apple-evidence">${evidence}</div>` : ""}</li>`;
  }

  function renderActions(viewModel) {
    const root = byId("action-phases");
    if (viewModel.actions.length === 0) {
      root.innerHTML = emptyTable("当前筛选暂无运营动作", "调整筛选条件查看其他生成行动。");
      return;
    }
    const phases = unique(viewModel.actions.map(function (item) { return item.phase; }));
    root.innerHTML = phases.map(function (phase) {
      const phaseActions = viewModel.actions.filter(function (item) { return item.phase === phase; });
      return `<section class="panel apple-action-phase" aria-label="${escape(phase)}">
        <header class="panel__header"><h3>${escape(phase)}</h3><span class="panel__meta">${escape(core.formatNumber(phaseActions.length))} 项</span></header>
        <div class="panel__body"><ol class="action-list">${phaseActions.map(function (item, index) {
          const target = item.target || {};
          const targets = [item.region, item.cohort && (COHORT_LABELS[item.cohort] || item.cohort), target.category, target.city, target.account_id].filter(Boolean);
          return `<li class="action-list__item apple-action">
            <span class="action-list__index">${String(index + 1).padStart(2, "0")}</span>
            <div class="apple-action__content">
              <div class="apple-action__title"><strong>${escape(item.title)}</strong><span class="status-badge ${item.priority === "high" ? "status--critical" : item.priority === "medium" ? "status--warning" : "status--unmatched"}">${escape(PRIORITY_LABELS[item.priority] || item.priority)}</span></div>
              <p>${escape(item.action)}</p>
              <div class="apple-action__meta"><code>${escape(item.rule_id)}</code><span>${escape(CONFIDENCE_LABELS[item.confidence] || item.confidence)}</span><span>影响经销商 ${escape(core.formatNumber(item.affected_dealer_count))}</span><span>影响账号 ${escape(core.formatNumber(item.affected_account_count))}</span></div>
              ${targets.length ? `<div class="apple-action__targets">${targets.map(function (target) { return `<span>${escape(target)}</span>`; }).join("")}</div>` : ""}
              <div class="apple-evidence">${asArray(item.evidence).map(renderEvidence).join("")}</div>
              ${asArray(item.top_examples).length ? `<details class="apple-examples"><summary>Top examples · ${escape(core.formatNumber(item.top_examples.length))}</summary><ul>${item.top_examples.map(renderExample).join("")}</ul></details>` : ""}
              ${asArray(item.drilldown_recommendation_ids).length ? `<details class="apple-drilldown-ids"><summary>完整追溯 ID · ${escape(core.formatNumber(item.drilldown_recommendation_ids.length))}</summary><ol aria-label="${escape(item.title)}完整追溯 ID">${item.drilldown_recommendation_ids.map(function (recommendationId) { return `<li><code>${escape(recommendationId)}</code></li>`; }).join("")}</ol></details>` : ""}
            </div>
          </li>`;
        }).join("")}</ol></div>
      </section>`;
    }).join("");
  }

  function setChartFallback(id, visible, message) {
    const fallback = byId(id);
    if (!fallback) {
      return;
    }
    if (message) {
      fallback.textContent = message;
    }
    fallback.hidden = !visible;
  }

  function clearCharts() {
    core.destroyCharts(chartMap);
    Object.keys(chartMap).forEach(function (key) { delete chartMap[key]; });
  }

  function renderCharts(viewModel) {
    clearCharts();
    const Chart = global.Chart;
    if (typeof Chart !== "function") {
      setChartFallback("status-fallback", true, "图表资源加载失败，状态明细仍可查看。");
      setChartFallback("quadrant-fallback", true, "图表资源加载失败，经销商分层表仍可查看。");
      setChartFallback("category-fallback", true, "图表资源加载失败，分类表现表仍可查看。");
      return;
    }
    const theme = core.chartTheme();

    try {
    if (viewModel.statuses.length) {
      setChartFallback("status-fallback", false);
      chartMap.status = new Chart(byId("status-chart"), {
        type: "bar",
        data: {
          labels: viewModel.statuses.map(function (item) { return item.label; }),
          datasets: [{ label: "账号数", data: viewModel.statuses.map(function (item) { return item.count; }), backgroundColor: [theme.colors.positive, theme.colors.info, theme.colors.warning, theme.colors.critical, theme.colors.muted] }],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false }, ticks: theme.ticks }, y: { beginAtZero: true, grid: theme.grid, ticks: theme.ticks } } },
      });
    } else {
      setChartFallback("status-fallback", true, "当前数据没有 KPI 状态分布。");
    }

    if (viewModel.quadrants.length) {
      setChartFallback("quadrant-fallback", false);
      const quadrantColors = {
        high_supply_high_efficiency: theme.colors.positive,
        low_supply_high_efficiency: theme.colors.info,
        high_supply_low_efficiency: theme.colors.warning,
        low_supply_low_efficiency: theme.colors.critical,
      };
      const quadrantSeries = buildQuadrantSeries(viewModel.quadrants);
      chartMap.quadrant = new Chart(byId("quadrant-chart"), {
        type: "scatter",
        data: { datasets: quadrantSeries.map(function (series) {
          return {
            label: `${QUADRANT_LABELS[series.quadrant] || series.quadrant} · ${COHORT_LABELS[series.cohort] || series.cohort}`,
            data: series.rows.map(function (item) { return { x: item.normalized_supply, y: item.normalized_efficiency, name: item.name, cohort: item.cohort }; }),
            backgroundColor: quadrantColors[series.quadrant] || theme.colors.muted,
            borderColor: series.cohort === "core_kpi" ? theme.colors.ink : theme.colors.info,
            borderWidth: series.cohort === "core_kpi" ? 1 : 2,
            pointStyle: series.cohort === "core_kpi" ? "circle" : "rectRounded",
            pointRadius: 5,
            pointHoverRadius: 7,
          };
        }) },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          parsing: false,
          plugins: { tooltip: { callbacks: { label: function (context) { return `${context.raw.name}: ${core.formatNumber(context.raw.x, { maximumFractionDigits: 2 })} / ${core.formatNumber(context.raw.y, { maximumFractionDigits: 2 })}`; } } } },
          scales: { x: { type: "logarithmic", title: { display: true, text: "标准化供给" }, grid: theme.grid, ticks: theme.ticks }, y: { type: "logarithmic", title: { display: true, text: "标准化效率" }, grid: theme.grid, ticks: theme.ticks } },
        },
      });
    } else {
      setChartFallback("quadrant-fallback", true, "当前筛选没有经销商分层数据。");
    }

    if (viewModel.categories.length) {
      setChartFallback("category-fallback", false);
      const labels = viewModel.categories.map(function (item) { return `${item.region} · ${COHORT_LABELS[item.cohort] || item.cohort} · ${item.category}`; });
      chartMap.category = new Chart(byId("category-chart"), {
        type: "bar",
        data: {
          labels: labels,
          datasets: [
            { type: "bar", label: "笔记数", data: viewModel.categories.map(function (item) { return item.notes; }), backgroundColor: theme.colors.info, yAxisID: "y" },
            { type: "line", label: "单篇阅读", data: viewModel.categories.map(function (item) { return item.reads_per_note; }), borderColor: theme.colors.positive, backgroundColor: theme.colors.positive, pointRadius: 3, yAxisID: "y1" },
          ],
        },
        options: { responsive: true, maintainAspectRatio: false, scales: { x: { grid: { display: false }, ticks: theme.ticks }, y: { beginAtZero: true, grid: theme.grid, ticks: theme.ticks }, y1: { beginAtZero: true, position: "right", grid: { drawOnChartArea: false }, ticks: theme.ticks } } },
      });
    } else {
      setChartFallback("category-fallback", true, "当前筛选没有分类表现数据。");
    }
    } catch (_error) {
      clearCharts();
      setChartFallback("status-fallback", true, "图表渲染失败，状态明细仍可查看。");
      setChartFallback("quadrant-fallback", true, "图表渲染失败，经销商分层表仍可查看。");
      setChartFallback("category-fallback", true, "图表渲染失败，分类表现表仍可查看。");
    }
  }

  function setContentVisibility(visible) {
    byId("dashboard-content").hidden = !visible;
    document.querySelectorAll("[data-apple-content]").forEach(function (section) { section.hidden = !visible; });
  }

  function renderDashboard() {
    const viewModel = buildAppleViewModel(payload, state, core);
    if (!viewModel) {
      clearCharts();
      const content = byId("dashboard-content");
      content.innerHTML = `<div class="empty-state"><strong>没有可显示的 Apple 网络数据</strong><span>请检查生成数据中的顶层 apple 契约。</span></div>`;
      setContentVisibility(false);
      content.hidden = false;
      return;
    }
    renderFilters(viewModel);
    renderIdentity(viewModel);
    renderKpis(viewModel);
    renderScope(viewModel);
    renderStatuses(viewModel);
    renderRisks(viewModel);
    renderQuadrants(viewModel);
    renderRegionalContent(viewModel);
    renderReplicableCases(viewModel);
    renderActions(viewModel);
    renderCharts(viewModel);
    setContentVisibility(true);
    core.initIcons();
    if (global.location && /(?:localhost|127\.0\.0\.1)/.test(global.location.hostname || "")) {
      console.assert(viewModel.reconciliation.ok, "Apple status_counts do not reconcile with account_counts.core_kpi", viewModel.reconciliation);
    }
  }

  function handleFilterChange(event) {
    const key = event.target.dataset.filterKey;
    if (!key) {
      return;
    }
    state[key] = event.target.value;
    renderDashboard();
  }

  function init() {
    const dataRoot = byId("data-state");
    core.renderLoading(dataRoot);
    core.initIcons();
    core.loadData().then(function (data) {
      payload = data;
      dataRoot.innerHTML = "";
      dataRoot.hidden = true;
      renderDashboard();
      document.querySelectorAll("[data-filter-key]").forEach(function (control) {
        control.addEventListener("change", handleFilterChange);
      });
    }).catch(function (error) {
      clearCharts();
      byId("report-month").textContent = "不可用";
      byId("freshness-badge").textContent = "加载失败";
      byId("quality-badge").textContent = "数据不可用";
      byId("quality-badge").className = "quality-badge status--critical";
      core.renderError(dataRoot, error);
      setContentVisibility(false);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})(window);
