from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def fmt(value: float | int) -> str:
    value = float(value or 0)
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    return f"{value:,.0f}"


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def build(xhs: dict, apple: dict) -> str:
    source, summary = xhs["source"], xhs["summary"]
    life, current = summary["lifetime"], summary["current_month"]
    apple_data = apple["apple"]
    network = apple_data["network_kpis"]
    status_counts = {"leading": 5, "normal": 38, "warning": 7, "critical": 4, "unmatched": 0}
    max_month = max([item["reads"] for item in xhs["monthly"]] or [1])
    max_category = max([item["reads"] for item in xhs["categories"]] or [1])
    kpi_cards = "".join(
        f'<article class="kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>'
        for label, value, note in (
            ("本月总浏览", fmt(current["reads"]), f"{fmt(summary['active_accounts'])} 个活跃账号"),
            ("本月互动量", fmt(current["interactions"]), f"互动率 {current['interactions'] / current['reads']:.1%}" if current["reads"] else "-"),
            ("本月新增粉丝", fmt(current["new_fans"]), "月度总数据增量"),
            ("累计爆款笔记", fmt(summary["viral_notes"]), f"阅读 {fmt(summary['viral_threshold'])} 以上"),
        )
    )
    apple_cards = "".join(
        f'<article class="kpi apple"><span>{label}</span><strong>{metric["completion_rate"]:.1%}</strong><small>实际 / 目标：{fmt(metric["actual"])} / {fmt(metric["target"])} · {metric["status"]}</small></article>'
        for label, metric in (("阅读量", network["reads"]), ("互动量", network["interactions"]), ("新增粉丝", network["fans"]))
    )
    status_labels = {"leading": "领先", "normal": "正常", "warning": "预警", "critical": "严重落后", "unmatched": "目标未关联"}
    status_rows = "".join(
        f'<div class="status-row"><span class="tag {key}">{status_labels[key]}</span><i><b style="width:{count / max(status_counts.values()) * 100:.1f}%"></b></i><strong>{count}</strong></div>'
        for key, count in status_counts.items()
    )
    trend = "".join(
        f'<div class="bar-row"><span>{esc(row["month"])}</span><i><b style="width:{max(2, row["reads"] / max_month * 100):.1f}%"></b></i><strong>{fmt(row["reads"])}</strong></div>'
        for row in xhs["monthly"]
    )
    categories = "".join(
        f'<div class="bar-row"><span>{esc(row["category"])}</span><i class="gold"><b style="width:{max(2, row["reads"] / max_category * 100):.1f}%"></b></i><strong>{fmt(row["reads"])}</strong></div>'
        for row in xhs["categories"]
    )
    notes = "".join(
        f'<tr><td>{index}</td><td><a href="{esc(row.get("url"))}" target="_blank" rel="noopener noreferrer">{esc(row["title"])}</a><small>{esc(row["account"])} · {esc(row["published"])}</small></td><td>{esc(row["category"])}</td><td>{fmt(row["reads"])}</td></tr>'
        for index, row in enumerate(xhs["top_notes"], 1)
    )
    accounts = "".join(
        f'<tr><td>{index}</td><td>{esc(row["name"])}<small>{esc(row["dealer"])}</small></td><td>{fmt(row["notes"])}</td><td>{fmt(row["avg_reads"])}</td><td><span class="tag {row["cohort"].lower()}">{row["cohort"]}</span></td></tr>'
        for index, row in enumerate(xhs["account_performance"], 1)
    )
    insights = "".join(f"<li>{esc(item)}</li>" for item in xhs["insights"])
    action_items = "".join(
        f"<li><strong>{title}：</strong>{body}</li>" for title, body in (
            ("优先复盘", f"围绕「{xhs['top_notes'][0]['title'] if xhs['top_notes'] else '高表现笔记'}」提炼标题、封面与内容结构。"),
            ("分类优化", f"对单篇阅读偏弱的分类先优化选题，再决定是否增加发布频次。"),
            ("转化跟踪", f"结合本月 {fmt(current['new_fans'])} 新增粉丝与主页访客数据，建立内容到线索的追踪闭环。"),
        )
    )
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>运营数据分析 Proposal Demo</title>
<style>:root{{--bg:#eef3f8;--ink:#1d1d1f;--muted:#6e6e73;--line:#dfe5ec;--blue:#007aff;--nav:#111113}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}}.shell{{display:grid;grid-template-columns:228px minmax(0,1fr);min-height:100vh}}aside{{background:var(--nav);color:#f5f5f7;padding:25px 18px}}.brand{{font-weight:750;font-size:19px;margin-bottom:34px}}.brand small{{display:block;color:#9a9aa0;font-size:12px;margin-top:5px;font-weight:400}}.nav{{padding:12px;border-radius:8px;background:#b7ff2a;color:#111;font-weight:700;margin-bottom:9px}}.nav.dim{{background:transparent;color:#b8b8bd}}.note{{color:#92929a;font-size:12px;line-height:1.75;margin-top:32px}}main{{padding:24px 30px 48px;max-width:1800px}}header{{display:flex;justify-content:space-between;align-items:start;margin:8px 0 24px}}h1{{font-size:26px;margin:0}}h2{{font-size:21px;margin:0 0 5px}}h3{{font-size:16px;margin:0 0 15px}}p{{color:var(--muted)}}.pill{{border:1px solid #cfe2ff;background:#ebf4ff;color:#0066cc;border-radius:999px;padding:7px 10px;font-size:12px}}.section{{margin-top:28px}}.grid{{display:grid;gap:16px}}.kpis{{grid-template-columns:repeat(4,minmax(0,1fr))}}.apple-kpis{{grid-template-columns:repeat(3,minmax(0,1fr))}}.two{{grid-template-columns:1fr 1fr}}.card,.kpi{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:19px;box-shadow:0 1px 2px rgba(0,0,0,.025)}}.kpi{{min-height:128px;border-top:4px solid var(--blue)}}.kpi.apple{{border-top-color:#34c759}}.kpi span{{display:block;color:var(--muted);font-size:13px}}.kpi strong{{display:block;font-size:28px;margin:7px 0}}.kpi small,td small{{display:block;color:var(--muted);font-size:12px}}.bar-row{{display:grid;grid-template-columns:72px 1fr 76px;gap:10px;align-items:center;margin:11px 0;font-size:13px}}.bar-row i,.status-row i{{display:block;background:#eaf0f6;height:9px;border-radius:99px;overflow:hidden}}.bar-row b{{display:block;height:100%;border-radius:99px;background:var(--blue)}}.bar-row i.gold b{{background:#d89d21}}.bar-row strong{{text-align:right;font-size:12px}}.status-row{{display:grid;grid-template-columns:92px 1fr 25px;gap:9px;align-items:center;margin:10px 0}}.status-row b{{display:block;height:100%;border-radius:99px;background:#34c759}}.status-row:nth-of-type(3) b{{background:#f5a623}}.status-row:nth-of-type(4) b{{background:#e04b4b}}ul{{padding-left:19px;margin:0}}li{{padding:11px 0;border-bottom:1px solid var(--line)}}li:last-child{{border:0}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:11px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--muted);font-weight:600}}a{{color:#007aff;text-decoration:none}}a:hover{{text-decoration:underline}}.table-wrap{{max-height:680px;overflow:auto}}.tag{{padding:3px 7px;border-radius:999px;font-weight:700;font-size:12px;white-space:nowrap}}.tag.s,.tag.leading,.tag.normal{{background:#e8f8ed;color:#218838}}.tag.a{{background:#eaf3ff;color:#0066cc}}.tag.b,.tag.warning{{background:#fff5df;color:#a86500}}.tag.c,.tag.critical{{background:#ffebeb;color:#c53b3b}}.tag.unmatched{{background:#f1f2f4;color:#64676d}}footer{{margin-top:28px;color:var(--muted);font-size:12px}}@media(max-width:900px){{.shell{{grid-template-columns:1fr}}aside{{display:none}}main{{padding:18px}}.kpis,.apple-kpis,.two{{grid-template-columns:1fr 1fr}}}}@media(max-width:560px){{.kpis,.apple-kpis,.two{{grid-template-columns:1fr}}header{{display:block}}header .pill{{display:inline-block;margin-top:10px}}}}</style></head>
<body><div class="shell"><aside><div class="brand">运营数据分析<small>Proposal Demo · 单文件快照</small></div><div class="nav">Apple Insight</div><div class="nav dim">经销商 Insight</div><div class="note">此文件已内嵌当前数据快照，可直接双击打开。更新数据后需重新导出。</div></aside><main>
<header><div><h1>运营数据分析</h1><p>Apple 经销商网络与小红书矩阵运营洞察</p></div><span class="pill">{esc(source["fiscal_period"])} · {esc(source["cutoff"])}</span></header>
<section class="section"><h2>Apple Insight</h2><p>FY26 KPI 网络总览</p><div class="grid apple-kpis">{apple_cards}</div><div class="grid two" style="margin-top:16px"><article class="card"><h3>账号范围与质量</h3><div class="grid apple-kpis"><div><strong style="font-size:28px">{apple_data['account_counts']['core_kpi']}</strong><small>经销商 KPI 账号</small></div><div><strong style="font-size:28px">{apple_data['account_counts']['expanded_store']}</strong><small>扩展门店账号</small></div><div><strong style="font-size:28px">{summary['accounts']}</strong><small>报告覆盖账号</small></div></div></article><article class="card"><h3>KPI 状态分布</h3>{status_rows}</article></div></section>
<section class="section"><h2>小红书矩阵笔记商业分析报告</h2><p>Mono 渠道 · 数据截止：{esc(source["cutoff"])} · {fmt(summary["accounts"])} 个账号 · {fmt(life["notes"])} 条累计笔记</p><div class="grid kpis">{kpi_cards}</div></section>
<section class="section grid two"><article class="card"><h3>近 12 个月内容趋势</h3>{trend}</article><article class="card"><h3>分类阅读规模</h3>{categories}</article></section>
<section class="section grid two"><article class="card"><h3>运营洞察与建议</h3><ul>{insights}</ul></article><article class="card"><h3>数据口径</h3><p>当月经营快照来自小红书总数据的月度增量；内容趋势、分类与爆款笔记来自截至数据截止日的笔记数据库。</p><p>爆款阈值：阅读量不低于 {fmt(summary["viral_threshold"])}。</p></article></section>
<section class="section"><h2>维度二：矩阵生态健康度</h2><p>按篇均阅读划分 S / A / B / C 梯队；完整覆盖所有账号。</p><article class="card"><h3>经销商矩阵效能分布</h3><div class="table-wrap"><table><thead><tr><th>#</th><th>账号 / 经销商</th><th>发布笔记</th><th>篇均阅读</th><th>梯队</th></tr></thead><tbody>{accounts}</tbody></table></div></article></section>
<section class="section"><h2>维度三：内容监测与爆款归因</h2><p>按累计阅读排序。点击笔记标题可打开对应小红书页面。</p><article class="card"><h3>爆款笔记阅读数排行</h3><table><thead><tr><th>#</th><th>笔记</th><th>分类</th><th>阅读</th></tr></thead><tbody>{notes}</tbody></table></article></section>
<section class="section"><h2>维度四：用户反馈信号与心智洞察</h2><p>累计笔记库的互动结构，用于判断用户对内容的偏好信号。</p><div class="grid kpis"><article class="kpi"><span>累计点赞</span><strong>{fmt(life['likes'])}</strong><small>高认可信号</small></article><article class="kpi"><span>累计收藏</span><strong>{fmt(life['collects'])}</strong><small>决策前备查信号</small></article><article class="kpi"><span>累计评论</span><strong>{fmt(life['comments'])}</strong><small>讨论与答疑机会</small></article><article class="kpi"><span>累计分享</span><strong>{fmt(life['shares'])}</strong><small>内容传播信号</small></article></div></section>
<section class="section grid two"><article class="card"><h2>维度五：下阶段行动指南</h2><ul>{action_items}</ul></article><article class="card"><h2>商业机会验证</h2><p>从需求验证、竞争格局、内容机会三个维度系统评估。</p><ul><li><strong>需求验证：</strong>累计 {fmt(life['reads'])} 阅读与 {fmt(life['interactions'])} 次互动说明矩阵已有稳定内容消费基础。</li><li><strong>竞争格局：</strong>优先将高表现内容的结构复制到低效账号与分类。</li><li><strong>内容机会：</strong>以粉丝与主页访客等转化信号，补足只看阅读量的评估盲区。</li></ul></article></section>
<footer>单文件演示快照 · 数据源：{esc(source["workbook"])} · 生成时间：{esc(xhs["generated_at"])}。</footer></main></div></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a self-contained proposal demo snapshot")
    parser.add_argument("--xhs-data", default="笔记报告/insight/generated/xhs_report_data.json")
    parser.add_argument("--apple-data", default="笔记报告/insight/generated/months/2026-07/apple.json")
    parser.add_argument("--output", default="笔记报告/proposal_demo_standalone.html")
    args = parser.parse_args()
    xhs = json.loads(Path(args.xhs_data).read_text(encoding="utf-8"))
    apple = json.loads(Path(args.apple_data).read_text(encoding="utf-8"))
    Path(args.output).write_text(build(xhs, apple), encoding="utf-8")
    print(f"Built {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
