(function (global) {
  "use strict";

  const KPI_DEFINITIONS = Object.freeze([
    { key: "reads", label: "阅读量" },
    { key: "interactions", label: "互动量" },
    { key: "fans", label: "新增粉丝" },
  ]);
  const FORMAT_DEFINITIONS = Object.freeze([
    { key: "image", label: "图文", notesKey: "image_notes", shareKey: "image_share" },
    { key: "video", label: "视频", notesKey: "video_notes", shareKey: "video_share" },
  ]);
  const PRIORITY_LABELS = Object.freeze({ high: "高优先级", medium: "中优先级", low: "低优先级" });
  const CONFIDENCE_LABELS = Object.freeze({ supported: "数据支持", signal: "观察信号", validate: "待验证" });
  const COHORT_LABELS = Object.freeze({ core_kpi: "核心 KPI", expanded_store: "扩展门店" });
  const ACCOUNT_CONFIDENCE = Object.freeze({
    confirmed: { label: "归属已确认", className: "status--normal" },
    inferred: { label: "推断归属", className: "status--warning" },
    unknown: { label: "归属待补充", className: "status--critical" },
  });
  const EVIDENCE_FORMATS = Object.freeze({
    city_confidence: "percent",
    fans_actual: "number",
    fans_completion: "percent",
    fans_pacing_gap: "points",
    interactions_actual: "number",
    interactions_completion: "percent",
    interactions_pacing_gap: "points",
    mapping_completeness: "percent",
    note_share: "percent",
    notes: "number",
    reads_actual: "number",
    reads_completion: "percent",
    reads_pacing_gap: "points",
    reads_per_note: "number",
  });
  const EVIDENCE_SCOPE_LABELS = Object.freeze({
    account: "账号",
    dealer_category: "经销商分类",
    dealer_core_kpi: "经销商核心 KPI",
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

  function selectDealer(dealers, dealerId) {
    return asArray(dealers).find(function (dealer) {
      return dealer && dealer.dealer_id === dealerId;
    }) || null;
  }

  function getFilterOptions(dealer) {
    if (!dealer) {
      return { cities: [], accounts: [], categories: [], formats: [] };
    }

    const accounts = asArray(dealer.accounts);
    const content = dealer.content || {};
    return {
      cities: unique(accounts.map(function (account) { return account.city; })),
      accounts: accounts.map(function (account) {
        return {
          value: account.author_id,
          label: account.account_name || account.store || account.author_id,
          city: account.city || "",
          cohort: account.cohort || "",
        };
      }),
      categories: unique(asArray(content.categories).map(function (item) { return item.category; })),
      formats: FORMAT_DEFINITIONS.filter(function (definition) {
        return hasValue(content[definition.notesKey]) || hasValue(content[definition.shareKey]);
      }).map(function (definition) {
        return { value: definition.key, label: definition.label };
      }),
    };
  }

  function filterAccounts(accounts, filters) {
    const state = filters || {};
    return asArray(accounts).filter(function (account) {
      return (!state.city || account.city === state.city)
        && (!state.accountId || account.author_id === state.accountId)
        && (!state.cohort || account.cohort === state.cohort);
    });
  }

  function filterCategories(categories, category) {
    return asArray(categories).filter(function (item) {
      return !category || item.category === category;
    });
  }

  function filterCityCohorts(rows, filters) {
    const state = filters || {};
    return asArray(rows).filter(function (row) {
      const categories = asArray(row && row.content && row.content.categories);
      return (!state.city || row.city === state.city)
        && (!state.cohort || row.cohort === state.cohort)
        && (!state.category || categories.some(function (item) { return item.category === state.category; }));
    });
  }

  function buildFormatViewModel(content, format, core) {
    const source = content || {};
    return FORMAT_DEFINITIONS.filter(function (definition) {
      return !format || definition.key === format;
    }).filter(function (definition) {
      return hasValue(source[definition.notesKey]) || hasValue(source[definition.shareKey]);
    }).map(function (definition) {
      return {
        key: definition.key,
        label: definition.label,
        notesRaw: source[definition.notesKey],
        shareRaw: source[definition.shareKey],
        notes: core.formatNumber(source[definition.notesKey]),
        share: core.formatPercent(source[definition.shareKey]),
      };
    });
  }

  function sumRows(rows, key) {
    return rows.reduce(function (total, row) {
      return total + (Number(row && row[key]) || 0);
    }, 0);
  }

  function aggregateCategoryRows(rows, denominatorNotes) {
    const grouped = new Map();
    asArray(rows).forEach(function (row) {
      if (!row || !row.category) {
        return;
      }
      if (!grouped.has(row.category)) {
        grouped.set(row.category, []);
      }
      grouped.get(row.category).push(row);
    });

    return Array.from(grouped.entries()).map(function (entry) {
      const categoryRows = entry[1];
      const notes = sumRows(categoryRows, "notes");
      const reads = sumRows(categoryRows, "reads");
      const interactions = sumRows(categoryRows, "interactions");
      const newFans = sumRows(categoryRows, "new_fans");
      const first = categoryRows[0] || {};
      return {
        category: entry[0],
        notes: notes,
        note_share: denominatorNotes ? notes / denominatorNotes : null,
        reads: reads,
        interactions: interactions,
        shares: sumRows(categoryRows, "shares"),
        new_fans: newFans,
        reads_per_note: notes ? reads / notes : null,
        interaction_rate: reads ? interactions / reads : null,
        fans_per_10k_reads: reads ? newFans * 10000 / reads : null,
        mapping_completeness: hasValue(first.mapping_completeness) ? first.mapping_completeness : null,
        blank_category_notes: sumRows(categoryRows, "blank_category_notes"),
        benchmark_note_share: categoryRows.length === 1 ? first.benchmark_note_share : null,
        benchmark_reads_per_note: categoryRows.length === 1 ? first.benchmark_reads_per_note : null,
        benchmark_confidence: categoryRows.length === 1 ? first.benchmark_confidence : null,
        benchmark_sample_size: categoryRows.length === 1 ? first.benchmark_sample_size : null,
      };
    });
  }

  function aggregateContentRows(rows) {
    const contentRows = asArray(rows).filter(Boolean);
    if (contentRows.length === 0) {
      return null;
    }
    const reads = sumRows(contentRows, "reads");
    const notes = sumRows(contentRows, "notes");
    const interactions = sumRows(contentRows, "interactions");
    const newFans = sumRows(contentRows, "new_fans");
    const imageNotes = sumRows(contentRows, "image_notes");
    const videoNotes = sumRows(contentRows, "video_notes");
    const visitorNumerator = contentRows.reduce(function (total, row) {
      return total + (Number(row.visitor_rate) || 0) * (Number(row.reads) || 0);
    }, 0);
    const categoryRows = contentRows.flatMap(function (row) { return asArray(row.categories); });
    return {
      reads: reads,
      notes: notes,
      interactions: interactions,
      reads_per_note: notes ? reads / notes : null,
      interaction_rate: reads ? interactions / reads : null,
      fans_per_10k_reads: reads ? newFans * 10000 / reads : null,
      visitor_rate: reads ? visitorNumerator / reads : null,
      shares: sumRows(contentRows, "shares"),
      new_fans: newFans,
      image_notes: imageNotes,
      video_notes: videoNotes,
      image_share: notes ? imageNotes / notes : null,
      video_share: notes ? videoNotes / notes : null,
      categories: aggregateCategoryRows(categoryRows, notes),
    };
  }

  function unavailableContentScope(reason, level) {
    return {
      available: false,
      reason: reason,
      level: level,
      dimension: "unsupported",
      values: null,
      categoriesAvailable: false,
      formatsAvailable: false,
      categories: [],
      formats: [],
    };
  }

  function buildContentScope(dealer, filters, core) {
    const state = filters || {};
    if (!dealer) {
      return unavailableContentScope("no_content_data", "dealer");
    }

    const selectedAccount = state.accountId
      ? asArray(dealer.accounts).find(function (account) { return account.author_id === state.accountId; })
      : null;
    if (state.accountId) {
      if (!selectedAccount) {
        return unavailableContentScope("no_content_data", "account");
      }
      if (state.category || state.format) {
        return unavailableContentScope("account_content_breakdown_unavailable", "account");
      }
      const metrics = selectedAccount.metrics || {};
      const reads = Number(metrics.reads) || 0;
      const interactions = (Number(metrics.likes) || 0) + (Number(metrics.collects) || 0) + (Number(metrics.comments) || 0);
      return {
        available: true,
        reason: "",
        level: "account",
        dimension: "account",
        values: {
          reads: metrics.reads,
          interactions: interactions,
          new_fans: metrics.new_fans,
          interaction_rate: reads ? interactions / reads : null,
          visitor_rate: reads ? (Number(metrics.visitors) || 0) / reads : null,
        },
        categoriesAvailable: false,
        formatsAvailable: false,
        categories: [],
        formats: [],
      };
    }

    if (state.category && state.format) {
      return unavailableContentScope("category_format_cross_breakdown_unavailable", state.city ? "city" : "dealer");
    }

    let baseContent;
    let level;
    if (state.city) {
      const cityContents = asArray(dealer.content && dealer.content.by_city_cohort).filter(function (row) {
        return row.city === state.city && (!state.cohort || row.cohort === state.cohort);
      }).map(function (row) { return row.content; });
      baseContent = aggregateContentRows(cityContents);
      level = "city";
    } else {
      baseContent = dealer.content || null;
      level = "dealer";
    }
    if (!baseContent) {
      return unavailableContentScope("no_content_data", level);
    }

    if (state.category) {
      const categories = filterCategories(baseContent.categories, state.category);
      if (categories.length === 0) {
        return unavailableContentScope("no_content_data", level);
      }
      return {
        available: true,
        reason: "",
        level: level,
        dimension: "category",
        values: aggregateCategoryRows(categories, baseContent.notes)[0],
        categoriesAvailable: true,
        formatsAvailable: false,
        categories: categories,
        formats: [],
      };
    }

    if (state.format) {
      const formats = buildFormatViewModel(baseContent, state.format, core);
      if (formats.length === 0) {
        return unavailableContentScope("no_content_data", level);
      }
      return {
        available: true,
        reason: "",
        level: level,
        dimension: "format",
        values: { notes: formats[0].notesRaw, note_share: formats[0].shareRaw },
        categoriesAvailable: false,
        formatsAvailable: true,
        categories: [],
        formats: formats,
      };
    }

    return {
      available: true,
      reason: "",
      level: level,
      dimension: "content",
      values: baseContent,
      categoriesAvailable: true,
      formatsAvailable: true,
      categories: asArray(baseContent.categories),
      formats: buildFormatViewModel(baseContent, "", core),
    };
  }

  function buildKpiViewModel(dealer, core) {
    if (!dealer || dealer.cohort !== "core_kpi" || !dealer.kpi) {
      return [];
    }

    const elapsed = dealer.kpi.elapsed_ratio;
    return KPI_DEFINITIONS.map(function (definition) {
      const metric = dealer.kpi[definition.key] || {};
      if (!hasValue(metric.target) || Number(metric.target) <= 0 || !hasValue(metric.completion_rate)) {
        return null;
      }
      return {
        key: definition.key,
        label: definition.label,
        actualRaw: metric.actual,
        targetRaw: metric.target,
        completionRaw: metric.completion_rate,
        pacingGapRaw: metric.pacing_gap,
        elapsedRaw: elapsed,
        actual: core.formatNumber(metric.actual),
        target: core.formatNumber(metric.target),
        completion: core.formatPercent(metric.completion_rate),
        pacingGap: core.formatSignedPoints(metric.pacing_gap),
        elapsed: core.formatPercent(elapsed),
        status: metric.status,
        statusLabel: core.statusLabel(metric.status),
      };
    }).filter(Boolean);
  }

  function buildExpandedStoreViewModel(dealer, core) {
    if (!dealer) {
      return [];
    }
    const expandedAccounts = asArray(dealer.accounts).filter(function (account) {
      return account.cohort === "expanded_store";
    });
    if (dealer.cohort !== "expanded_store" && expandedAccounts.length === 0) {
      return [];
    }

    const metrics = dealer.expanded_store_metrics || {};
    return [
      { key: "reads", label: "阅读量", value: core.formatNumber(metrics.reads), raw: metrics.reads },
      { key: "interactions", label: "互动量", value: core.formatNumber(metrics.interactions), raw: metrics.interactions },
      { key: "interaction_rate", label: "互动率", value: core.formatPercent(metrics.interaction_rate), raw: metrics.interaction_rate },
      { key: "fans_per_10k_reads", label: "万阅涨粉", value: core.formatNumber(metrics.fans_per_10k_reads, { maximumFractionDigits: 1 }), raw: metrics.fans_per_10k_reads },
      { key: "visitor_rate", label: "主页访问率", value: core.formatPercent(metrics.visitor_rate), raw: metrics.visitor_rate },
    ];
  }

  function filterRecommendations(recommendations, filters) {
    const state = filters || {};
    const dimensions = [
      ["category", state.category],
      ["city", state.city],
      ["account_id", state.accountId],
    ];
    const hasScopedFilter = dimensions.some(function (entry) { return Boolean(entry[1]); });

    return asArray(recommendations).filter(function (recommendation) {
      const target = recommendation && recommendation.target ? recommendation.target : {};
      const targeted = dimensions.filter(function (entry) { return Boolean(target[entry[0]]); });
      if (!hasScopedFilter) {
        return true;
      }
      if (targeted.length === 0) {
        return true;
      }
      return targeted.every(function (entry) {
        return Boolean(entry[1]) && target[entry[0]] === entry[1];
      });
    });
  }

  function renderExpandedStore(section, root, metrics, core) {
    if (!section || !root) {
      return;
    }
    root.innerHTML = "";
    if (asArray(metrics).length === 0) {
      section.hidden = true;
      return;
    }
    section.hidden = false;
    root.innerHTML = metrics.map(function (item) {
      return core.renderMetricCard({ label: item.label, value: item.value, context: [{ label: "口径", value: "经营观察" }] });
    }).join("");
  }

  function formatEvidenceValue(metric, value, core) {
    if (!hasValue(value)) {
      return "-";
    }
    const format = EVIDENCE_FORMATS[metric] || "number";
    if (format === "points") {
      return core.formatSignedPoints(value);
    }
    if (format === "percent") {
      return core.formatPercent(value);
    }
    return core.formatNumber(value, { maximumFractionDigits: 1 });
  }

  function buildEvidenceViewModel(evidence, core) {
    const item = evidence || {};
    return {
      metric: item.metric || "",
      value: formatEvidenceValue(item.metric, item.value, core),
      benchmark: formatEvidenceValue(item.metric, item.benchmark, core),
      scope: item.scope || "",
      scopeLabel: EVIDENCE_SCOPE_LABELS[item.scope] || item.scope || "范围未标注",
    };
  }

  function renderEvidenceItem(evidence, core, escapeHtml) {
    const view = buildEvidenceViewModel(evidence, core);
    const escapeValue = typeof escapeHtml === "function" ? escapeHtml : String;
    return `<span><b>${escapeValue(view.metric)}</b> ${escapeValue(view.value)} / ${escapeValue(view.benchmark)} <em>${escapeValue(view.scopeLabel)}</em></span>`;
  }

  function buildAccountTableViewModel(dealer, accounts, core) {
    const statusByAccount = new Map(asArray(dealer && dealer.kpi && dealer.kpi.account_statuses).map(function (item) {
      return [item.author_id, item.status];
    }));
    return asArray(accounts).map(function (account) {
      const metrics = account.metrics || {};
      const interactions = (Number(metrics.likes) || 0) + (Number(metrics.collects) || 0) + (Number(metrics.comments) || 0);
      const status = statusByAccount.get(account.author_id);
      const confidence = ACCOUNT_CONFIDENCE[account.confidence] || ACCOUNT_CONFIDENCE.unknown;
      return {
        authorId: account.author_id,
        name: account.account_name || account.store || account.author_id,
        store: account.store || "",
        city: account.city || "待补充区域",
        cohort: account.cohort,
        cohortLabel: COHORT_LABELS[account.cohort] || account.cohort,
        reads: core.formatNumber(metrics.reads),
        interactions: core.formatNumber(interactions),
        newFans: core.formatNumber(metrics.new_fans),
        status: account.cohort === "core_kpi" ? status : "",
        statusLabel: account.cohort === "core_kpi" && status ? core.statusLabel(status) : "内容观察",
        statusClass: account.cohort === "core_kpi" && status ? core.statusClass(status) : "status--unmatched",
        confidence: account.confidence || "unknown",
        confidenceLabel: confidence.label,
        confidenceClass: confidence.className,
      };
    });
  }

  function buildDealerViewModel(data, filters, core) {
    const state = filters || {};
    const scopedDealer = data && data.dealer;
    const dealer = scopedDealer && scopedDealer.dealer_id === state.dealerId
      ? scopedDealer
      : selectDealer(data && data.dealers, state.dealerId);
    if (!dealer) {
      return null;
    }

    const options = getFilterOptions(dealer);
    const contentScope = buildContentScope(dealer, state, core);
    return {
      sourceMonth: data.source_month,
      generatedAt: data.generated_at,
      dataFreshness: data.data_freshness || (data.metadata && data.metadata.data_freshness),
      dealerOptions: asArray(data.dealer_options || data.dealers).map(function (item) {
        return { value: item.dealer_id, label: item.name };
      }),
      dealer: dealer,
      filters: {
        dealerId: state.dealerId || "",
        city: state.city || "",
        accountId: state.accountId || "",
        format: state.format || "",
        category: state.category || "",
        cohort: state.cohort || "",
      },
      options: options,
      accounts: filterAccounts(dealer.accounts, state),
      contentScope: contentScope,
      categories: contentScope.categories,
      cityCohorts: filterCityCohorts(dealer.content && dealer.content.by_city_cohort, state),
      formats: contentScope.formats,
      kpis: buildKpiViewModel(dealer, core),
      expandedStore: buildExpandedStoreViewModel(dealer, core),
      recommendations: filterRecommendations(dealer.recommendations, state),
    };
  }

  const api = Object.freeze({
    selectDealer,
    getFilterOptions,
    filterAccounts,
    filterCategories,
    filterCityCohorts,
    buildFormatViewModel,
    buildContentScope,
    buildKpiViewModel,
    buildExpandedStoreViewModel,
    filterRecommendations,
    renderExpandedStore,
    formatEvidenceValue,
    buildEvidenceViewModel,
    renderEvidenceItem,
    buildAccountTableViewModel,
    buildDealerViewModel,
  });
  global.DealerDashboard = api;

  if (!global.document || !global.InsightCore) {
    return;
  }

  const document = global.document;
  const core = global.InsightCore;
  const state = { dealerId: "", city: "", accountId: "", format: "", category: "", cohort: "" };
  let payload = null;
  let dealerIndex = null;
  let dealerRequestVersion = 0;

  function byId(id) {
    return document.getElementById(id);
  }

  function escape(value) {
    return core.escapeHtml(value);
  }

  function displayMonth(value) {
    const parts = String(value || "").split("-");
    if (parts.length !== 2) {
      return "月份未知";
    }
    return `${parts[0]}年${Number(parts[1])}月`;
  }

  function displayFreshness(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "更新时间未知";
    }
    return `更新于 ${new Intl.DateTimeFormat("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date)}`;
  }

  function optionHtml(item, selected) {
    return `<option value="${escape(item.value)}"${item.value === selected ? " selected" : ""}>${escape(item.label)}</option>`;
  }

  function setOptions(id, items, selected, allLabel) {
    const element = byId(id);
    if (!element) {
      return;
    }
    element.innerHTML = `<option value="">${escape(allLabel)}</option>${items.map(function (item) {
      return optionHtml(typeof item === "string" ? { value: item, label: item } : item, selected);
    }).join("")}`;
    element.value = selected || "";
  }

  function renderFilters(viewModel) {
    const cityAccounts = viewModel.options.accounts.filter(function (account) {
      return !state.city || account.city === state.city;
    });
    const dealerSelect = byId("dealer-filter");
    dealerSelect.innerHTML = viewModel.dealerOptions.map(function (item) {
      return optionHtml(item, state.dealerId);
    }).join("");
    dealerSelect.value = state.dealerId;
    setOptions("city-filter", viewModel.options.cities, state.city, "全部城市");
    setOptions("account-filter", cityAccounts, state.accountId, "全部账号");
    setOptions("format-filter", viewModel.options.formats, state.format, "全部形式");
    setOptions("category-filter", viewModel.options.categories, state.category, "全部分类");
    document.querySelectorAll(".filter-control").forEach(function (control) { control.disabled = false; });
    const accountSelected = Boolean(state.accountId);
    const categorySelected = Boolean(state.category);
    const formatSelected = Boolean(state.format);
    const categoryControl = byId("category-filter");
    const formatControl = byId("format-filter");
    categoryControl.disabled = accountSelected || formatSelected;
    formatControl.disabled = accountSelected || categorySelected;
    categoryControl.title = accountSelected ? "账号粒度无分类明细" : formatSelected ? "当前数据无形式与分类交叉明细" : "";
    formatControl.title = accountSelected ? "账号粒度无形式明细" : categorySelected ? "当前数据无分类与形式交叉明细" : "";
    const compatibility = byId("filter-compatibility");
    if (compatibility) {
      compatibility.hidden = !(accountSelected || categorySelected || formatSelected);
      compatibility.textContent = accountSelected
        ? "账号粒度仅展示账号经营快照，分类与内容形式不可用。"
        : categorySelected
          ? "分类范围无内容形式交叉明细，内容形式筛选已禁用。"
          : formatSelected
            ? "内容形式范围无分类交叉明细，统一分类筛选已禁用。"
            : "";
    }
  }

  function renderIdentity(viewModel) {
    const dealer = viewModel.dealer;
    byId("dealer-name").textContent = dealer.name || "经销商";
    byId("dealer-cohort").textContent = COHORT_LABELS[dealer.cohort] || dealer.cohort || "范围待确认";
    byId("dealer-cohort").className = `status-badge ${dealer.cohort === "core_kpi" ? "status--normal" : "status--unmatched"}`;
    byId("report-month").textContent = displayMonth(viewModel.sourceMonth);
    byId("freshness-badge").textContent = displayFreshness(viewModel.dataFreshness && viewModel.dataFreshness.source_snapshot_at);
    const accountCount = asArray(dealer.accounts).length;
    const cityCount = viewModel.options.cities.length;
    byId("scope-badge").textContent = `${core.formatNumber(accountCount)} 个账号 · ${core.formatNumber(cityCount)} 个城市`;

    const firstAction = viewModel.recommendations[0];
    const summary = byId("operating-summary");
    if (firstAction) {
      summary.innerHTML = `<strong>${escape(firstAction.title)}</strong><span>${escape(firstAction.action)}</span>`;
    } else {
      summary.innerHTML = `<div class="empty-state dealer-empty"><strong>当前筛选暂无运营摘要</strong><span>调整筛选条件后查看数据中的可用建议。</span></div>`;
    }
  }

  function metricCard(label, value, context) {
    return core.renderMetricCard({ label: label, value: value, context: context || [] });
  }

  function renderKpis(viewModel) {
    const root = byId("kpi-cards");
    const progress = byId("kpi-progress-list");
    if (viewModel.kpis.length === 0) {
      root.innerHTML = `<div class="state-panel dealer-span-full"><strong>该经销商没有关联核心 KPI 目标</strong><span>扩展门店数据在下方作为内容与经营观察单独展示。</span></div>`;
      progress.innerHTML = `<div class="empty-state"><strong>无核心 KPI 进度</strong><span>本范围不展示 FY26 目标完成率。</span></div>`;
      return;
    }

    root.innerHTML = viewModel.kpis.map(function (item) {
      return core.renderMetricCard({
        label: item.label,
        value: item.completion,
        status: item.status,
        context: [
          { label: "实际 / 目标", value: `${item.actual} / ${item.target}` },
          { label: "时间进度", value: item.elapsed },
          { label: "节奏偏差", value: item.pacingGap },
        ],
      });
    }).join("");

    progress.innerHTML = viewModel.kpis.map(function (item) {
      const completion = Math.max(0, Math.min(100, Number(item.completionRaw) * 100 || 0));
      const elapsed = Math.max(0, Math.min(100, Number(item.elapsedRaw) * 100 || 0));
      return `<article class="dealer-bullet">
        <div class="dealer-bullet__head">
          <div><strong>${escape(item.label)}</strong><span>${escape(item.actual)} / ${escape(item.target)}</span></div>
          <span class="status-badge ${core.statusClass(item.status)}">${escape(item.statusLabel)}</span>
        </div>
        <div class="dealer-bullet__track" role="img" aria-label="${escape(item.label)}完成率 ${escape(item.completion)}，时间进度 ${escape(item.elapsed)}">
          <span class="dealer-bullet__fill ${core.statusClass(item.status)}" style="width:${completion}%"></span>
          <span class="dealer-bullet__pace" style="left:${elapsed}%" aria-hidden="true"></span>
        </div>
        <div class="dealer-bullet__foot"><span>完成 ${escape(item.completion)}</span><span>节奏 ${escape(item.pacingGap)}</span></div>
      </article>`;
    }).join("");
  }

  function renderOperatingMetrics(viewModel) {
    const scoped = viewModel.contentScope;
    const values = scoped.values;
    const root = byId("operating-metrics");
    if (!scoped.available || !values) {
      root.innerHTML = `<div class="empty-state dealer-span-full"><strong>当前筛选组合不可用</strong><span>${escape(scopeUnavailableMessage(scoped.reason))}</span></div>`;
      return;
    }
    let definitions;
    if (scoped.dimension === "account") {
      definitions = [
      ["阅读量", core.formatNumber(values.reads)],
      ["互动量", core.formatNumber(values.interactions)],
      ["新增粉丝", core.formatNumber(values.new_fans)],
      ["互动率", core.formatPercent(values.interaction_rate)],
      ["主页访问率", core.formatPercent(values.visitor_rate)],
      ];
    } else if (scoped.dimension === "format") {
      definitions = [
        ["发布笔记", core.formatNumber(values.notes)],
        ["供给占比", core.formatPercent(values.note_share)],
      ];
    } else {
      definitions = [
        ["发布笔记", core.formatNumber(values.notes)],
        ["单篇阅读", core.formatNumber(values.reads_per_note, { maximumFractionDigits: 1 })],
        ["互动率", core.formatPercent(values.interaction_rate)],
        ["万阅涨粉", core.formatNumber(values.fans_per_10k_reads, { maximumFractionDigits: 1 })],
      ];
      if (hasValue(values.visitor_rate)) {
        definitions.push(["主页访问率", core.formatPercent(values.visitor_rate)]);
      }
    }
    root.innerHTML = definitions.map(function (item) { return metricCard(item[0], item[1]); }).join("");
  }

  function renderContentScopeLabels(viewModel) {
    const scope = viewModel.contentScope;
    const levelLabels = { dealer: "经销商", city: "城市", account: "账号" };
    const dimensionLabels = { content: "全部内容", category: "分类", format: "内容形式", account: "经营快照", unsupported: "不可用组合" };
    const label = `${levelLabels[scope.level] || scope.level} · ${dimensionLabels[scope.dimension] || scope.dimension}`;
    byId("operating-scope-meta").textContent = label;
    byId("category-scope-meta").textContent = scope.categoriesAvailable ? label : "当前范围不可用";
    byId("format-scope-meta").textContent = scope.formatsAvailable ? label : "当前范围不可用";
  }

  function renderExpanded(viewModel) {
    renderExpandedStore(byId("expanded-store-section"), byId("expanded-store-metrics"), viewModel.expandedStore, core);
  }

  function scopeUnavailableMessage(reason) {
    const messages = {
      account_content_breakdown_unavailable: "账号粒度没有分类或内容形式明细，请清除不支持的筛选组合。",
      category_format_cross_breakdown_unavailable: "当前数据没有分类与内容形式的交叉明细。",
      no_content_data: "当前范围没有可用内容数据。",
    };
    return messages[reason] || messages.no_content_data;
  }

  function renderCategoryTable(viewModel) {
    const root = byId("category-table");
    if (!viewModel.contentScope.categoriesAvailable) {
      root.innerHTML = `<div class="empty-state"><strong>当前范围无分类明细</strong><span>${escape(scopeUnavailableMessage(viewModel.contentScope.reason || (viewModel.contentScope.dimension === "format" ? "category_format_cross_breakdown_unavailable" : "account_content_breakdown_unavailable")))}</span></div>`;
      return;
    }
    if (viewModel.categories.length === 0) {
      root.innerHTML = `<div class="empty-state"><strong>当前筛选无分类数据</strong><span>调整分类筛选后查看。</span></div>`;
      return;
    }
    root.innerHTML = `<div class="table-scroll"><table class="data-table dealer-category-table">
      <thead><tr><th>分类</th><th data-align="right">笔记</th><th data-align="right">供给占比</th><th data-align="right">同组占比</th><th data-align="right">单篇阅读</th><th data-align="right">同组单篇阅读</th><th>置信度</th></tr></thead>
      <tbody>${viewModel.categories.map(function (item) {
        return `<tr><td>${escape(item.category)}</td><td data-align="right">${escape(core.formatNumber(item.notes))}</td><td data-align="right">${escape(core.formatPercent(item.note_share))}</td><td data-align="right">${escape(core.formatPercent(item.benchmark_note_share))}</td><td data-align="right">${escape(core.formatNumber(item.reads_per_note, { maximumFractionDigits: 1 }))}</td><td data-align="right">${escape(core.formatNumber(item.benchmark_reads_per_note, { maximumFractionDigits: 1 }))}</td><td>${escape(CONFIDENCE_LABELS[item.benchmark_confidence] || item.benchmark_confidence || "-")}</td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderFormatTable(viewModel) {
    const root = byId("format-table");
    if (!viewModel.contentScope.formatsAvailable) {
      root.innerHTML = `<div class="empty-state"><strong>当前范围无内容形式明细</strong><span>${escape(scopeUnavailableMessage(viewModel.contentScope.reason || (viewModel.contentScope.dimension === "category" ? "category_format_cross_breakdown_unavailable" : "account_content_breakdown_unavailable")))}</span></div>`;
      return;
    }
    if (viewModel.formats.length === 0) {
      root.innerHTML = `<div class="empty-state"><strong>当前筛选无形式数据</strong><span>调整内容形式筛选后查看。</span></div>`;
      return;
    }
    root.innerHTML = `<div class="dealer-format-list">${viewModel.formats.map(function (item) {
      return `<div class="dealer-format-row"><strong>${escape(item.label)}</strong><span>${escape(item.notes)} 篇</span><span>${escape(item.share)}</span></div>`;
    }).join("")}</div>`;
  }

  function renderCityAccounts(viewModel) {
    const root = byId("account-table");
    if (viewModel.accounts.length === 0) {
      root.innerHTML = `<div class="empty-state"><strong>当前筛选无账号</strong><span>调整城市或账号筛选后查看。</span></div>`;
      return;
    }
    const rows = buildAccountTableViewModel(viewModel.dealer, viewModel.accounts, core);
    root.innerHTML = `<div class="table-scroll"><table class="data-table dealer-account-table">
      <thead><tr><th>账号 / 门店</th><th>城市</th><th>归属置信度</th><th>分层</th><th data-align="right">阅读</th><th data-align="right">互动</th><th data-align="right">新增粉丝</th><th>状态</th></tr></thead>
      <tbody>${rows.map(function (row) {
        return `<tr><td><strong>${escape(row.name)}</strong><small>${escape(row.store)}</small></td><td>${escape(row.city)}</td><td><span class="status-badge ${row.confidenceClass}">${escape(row.confidenceLabel)}</span></td><td>${escape(row.cohortLabel)}</td><td data-align="right">${escape(row.reads)}</td><td data-align="right">${escape(row.interactions)}</td><td data-align="right">${escape(row.newFans)}</td><td><span class="status-badge ${row.statusClass}">${escape(row.statusLabel)}</span></td></tr>`;
      }).join("")}</tbody>
    </table></div>`;
  }

  function renderActions(viewModel) {
    const root = byId("action-list");
    if (viewModel.recommendations.length === 0) {
      root.innerHTML = `<div class="empty-state"><strong>当前筛选暂无建议</strong><span>调整筛选条件查看其他数据驱动建议。</span></div>`;
      return;
    }
    root.innerHTML = `<ol class="action-list">${viewModel.recommendations.map(function (item, index) {
      const target = item.target || {};
      const targets = [target.category, target.city, target.account_id].filter(Boolean);
      return `<li class="action-list__item dealer-action">
        <span class="action-list__index">${String(index + 1).padStart(2, "0")}</span>
        <div class="dealer-action__content">
          <div class="dealer-action__title"><strong>${escape(item.title)}</strong><span class="status-badge ${item.priority === "high" ? "status--critical" : item.priority === "medium" ? "status--warning" : "status--unmatched"}">${escape(PRIORITY_LABELS[item.priority] || item.priority)}</span></div>
          <p>${escape(item.action)}</p>
          ${targets.length ? `<div class="dealer-action__targets">${targets.map(function (targetValue) { return `<span>${escape(targetValue)}</span>`; }).join("")}</div>` : ""}
          <div class="dealer-evidence">${asArray(item.evidence).map(function (evidence) {
            return renderEvidenceItem(evidence, core, escape);
          }).join("")}</div>
        </div>
        <span class="dealer-action__confidence">${escape(CONFIDENCE_LABELS[item.confidence] || item.confidence)}</span>
      </li>`;
    }).join("")}</ol>`;
  }

  function chartFallback(id, visible) {
    const element = byId(id);
    if (element) {
      element.hidden = !visible;
    }
  }

  function renderCharts(viewModel) {
    core.destroyCharts(chartMap);
    Object.keys(chartMap).forEach(function (key) { delete chartMap[key]; });
    const Chart = global.Chart;

    try {
    if (!viewModel.contentScope.categoriesAvailable || typeof Chart !== "function" || viewModel.categories.length === 0) {
      const fallback = byId("category-chart-fallback");
      fallback.textContent = viewModel.contentScope.categoriesAvailable ? "图表不可用，分类明细表仍可查看。" : "当前筛选范围没有分类明细。";
      chartFallback("category-chart-fallback", true);
    } else {
      chartFallback("category-chart-fallback", false);
      const theme = core.chartTheme();
      chartMap.category = new Chart(byId("category-chart"), {
        type: "scatter",
        data: {
          datasets: [{
            label: viewModel.dealer.name,
            data: viewModel.categories.map(function (item) {
              return { x: Number(item.note_share) * 100, y: Number(item.reads_per_note), label: item.category };
            }),
            backgroundColor: theme.colors.positive,
            borderColor: theme.colors.ink,
            pointRadius: 6,
            pointHoverRadius: 7,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          parsing: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: function (context) { return `${context.raw.label}: ${context.raw.x.toFixed(1)}% / ${core.formatNumber(context.raw.y, { maximumFractionDigits: 1 })}`; } } },
          },
          scales: {
            x: { title: { display: true, text: "供给占比 (%)" }, grid: theme.grid, ticks: theme.ticks },
            y: { title: { display: true, text: "单篇阅读" }, grid: theme.grid, ticks: theme.ticks },
          },
        },
      });
    }

    if (!viewModel.contentScope.formatsAvailable || typeof Chart !== "function" || viewModel.formats.length === 0) {
      const fallback = byId("format-chart-fallback");
      fallback.textContent = viewModel.contentScope.formatsAvailable ? "图表不可用，形式明细仍可查看。" : "当前筛选范围没有内容形式明细。";
      chartFallback("format-chart-fallback", true);
    } else {
      chartFallback("format-chart-fallback", false);
      const theme = core.chartTheme();
      chartMap.format = new Chart(byId("format-chart"), {
        type: "bar",
        data: {
          labels: viewModel.formats.map(function (item) { return item.label; }),
          datasets: [{ label: "笔记数", data: viewModel.formats.map(function (item) { return item.notesRaw; }), backgroundColor: [theme.colors.info, theme.colors.positive] }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { grid: { display: false }, ticks: theme.ticks }, y: { beginAtZero: true, grid: theme.grid, ticks: theme.ticks } },
        },
      });
    }
    } catch (_error) {
      core.destroyCharts(chartMap);
      Object.keys(chartMap).forEach(function (key) { delete chartMap[key]; });
      byId("category-chart-fallback").textContent = "图表渲染失败，分类明细表仍可查看。";
      byId("format-chart-fallback").textContent = "图表渲染失败，形式明细仍可查看。";
      chartFallback("category-chart-fallback", true);
      chartFallback("format-chart-fallback", true);
    }
  }

  function renderDashboard() {
    const viewModel = buildDealerViewModel(payload, state, core);
    if (!viewModel) {
      core.destroyCharts(chartMap);
      Object.keys(chartMap).forEach(function (key) { delete chartMap[key]; });
      const content = byId("dashboard-content");
      content.innerHTML = `<div class="empty-state"><strong>没有可显示的经销商数据</strong><span>请检查生成数据中的 dealers 列表。</span></div>`;
      content.hidden = false;
      return;
    }
    renderFilters(viewModel);
    renderIdentity(viewModel);
    renderKpis(viewModel);
    renderContentScopeLabels(viewModel);
    renderOperatingMetrics(viewModel);
    renderExpanded(viewModel);
    renderCategoryTable(viewModel);
    renderFormatTable(viewModel);
    renderCityAccounts(viewModel);
    renderActions(viewModel);
    renderCharts(viewModel);
    byId("dashboard-content").hidden = false;
    core.initIcons();
  }

  function handleFilterChange(event) {
    const key = event.target.dataset.filterKey;
    if (!key) {
      return;
    }
    state[key] = event.target.value;
    if (key === "dealerId") {
      state.city = "";
      state.accountId = "";
      state.format = "";
      state.category = "";
      const url = new URL(global.location.href);
      url.searchParams.set("dealer_id", state.dealerId);
      global.history.replaceState({}, "", url);
      return loadSelectedDealer(state.dealerId);
    }
    if (key === "city") {
      const dealer = selectDealer(payload.dealers, state.dealerId);
      const validAccounts = filterAccounts(dealer && dealer.accounts, { city: state.city });
      if (state.accountId && !validAccounts.some(function (account) { return account.author_id === state.accountId; })) {
        state.accountId = "";
      }
    }
    if (key === "accountId" && state.accountId) {
      state.category = "";
      state.format = "";
    }
    if (key === "category" && state.category) {
      state.format = "";
    }
    if (key === "format" && state.format) {
      state.category = "";
    }
    renderDashboard();
  }

  function loadSelectedDealer(dealerId) {
    const dataRoot = byId("data-state");
    const requestVersion = ++dealerRequestVersion;
    return core.loadData(`generated/dealers/${encodeURIComponent(dealerId)}.json`).then(function (scoped) {
      if (requestVersion !== dealerRequestVersion) {
        return;
      }
      if (!scoped.dealer || scoped.dealer.dealer_id !== dealerId) {
        throw new Error("经销商数据与请求范围不一致。");
      }
      payload = {
        ...scoped,
        dealer_options: asArray(dealerIndex && dealerIndex.dealers),
      };
      dataRoot.innerHTML = "";
      dataRoot.hidden = true;
      renderDashboard();
    }).catch(function (error) {
      if (requestVersion !== dealerRequestVersion) {
        return;
      }
      byId("report-month").textContent = "不可用";
      byId("freshness-badge").textContent = "加载失败";
      core.renderError(dataRoot, error);
      byId("dashboard-content").hidden = true;
    });
  }

  function init() {
    const dataRoot = byId("data-state");
    core.renderLoading(dataRoot);
    core.initIcons();
    core.loadData("generated/dealer_index.json").then(function (data) {
      dealerIndex = data;
      const requestedDealer = new URL(global.location.href).searchParams.get("dealer_id");
      const firstDealer = asArray(data.dealers)[0];
      state.dealerId = selectDealer(data.dealers, requestedDealer) ? requestedDealer : (firstDealer && firstDealer.dealer_id) || "";
      document.querySelectorAll("[data-filter-key]").forEach(function (control) {
        control.addEventListener("change", handleFilterChange);
      });
      if (!state.dealerId) {
        payload = { ...data, dealer_options: [], dealers: [] };
        dataRoot.innerHTML = "";
        dataRoot.hidden = true;
        renderDashboard();
        return;
      }
      return loadSelectedDealer(state.dealerId);
    }).catch(function (error) {
      byId("report-month").textContent = "不可用";
      byId("freshness-badge").textContent = "加载失败";
      core.renderError(dataRoot, error);
      byId("dashboard-content").hidden = true;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})(window);
