from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


def fmt(value: float | int) -> str:
    value = float(value or 0)
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    return f"{value:,.0f}"


def inline_report(report_path: Path, report_data: dict) -> str:
    source = report_path.read_text(encoding="utf-8")
    data_literal = json.dumps(report_data, ensure_ascii=False).replace("</", "<\\/")
    replacement = f"const fetchReport = async () => ({data_literal});"
    pattern = r"const fetchReport = async \(\) => \{[\s\S]*?\n    \};"
    result, count = re.subn(pattern, replacement, source, count=1)
    if count != 1:
        raise RuntimeError("Could not inline the report dataset")
    return result.replace("</head>", '<script>document.documentElement.dataset.embed = "apple";</script></head>', 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the current Proposal as a single self-contained HTML file")
    parser.add_argument("--xhs-report", default="笔记报告/xhs_report.html")
    parser.add_argument("--xhs-data", default="笔记报告/insight/generated/xhs_report_data.json")
    parser.add_argument("--apple-data", default="笔记报告/insight/generated/months/2026-07/apple.json")
    parser.add_argument("--output", default="笔记报告/proposal_demo_standalone.html")
    args = parser.parse_args()

    report_data = json.loads(Path(args.xhs_data).read_text(encoding="utf-8"))
    apple_data = json.loads(Path(args.apple_data).read_text(encoding="utf-8"))["apple"]
    report_document = inline_report(Path(args.xhs_report), report_data)
    srcdoc = html.escape(report_document, quote=True)
    network = apple_data["network_kpis"]
    account_counts = apple_data["account_counts"]
    status_counts = {"领先": 5, "正常": 38, "预警": 7, "严重落后": 4, "目标未关联": 0}
    status_rows = "".join(
        f'<div class="status"><span>{label}</span><i><b style="width:{count / 38 * 100:.1f}%"></b></i><strong>{count}</strong></div>'
        for label, count in status_counts.items()
    )
    cards = "".join(
        f'<article><span>{label}</span><strong>{metric["completion_rate"]:.1%}</strong><small>实际 / 目标：{fmt(metric["actual"])} / {fmt(metric["target"])} </small></article>'
        for label, metric in (("阅读量", network["reads"]), ("互动量", network["interactions"]), ("新增粉丝", network["fans"]))
    )
    source = report_data["source"]
    output = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>运营数据分析 Proposal Demo</title>
<style>:root{{--bg:#eef3f8;--ink:#1d1d1f;--muted:#6e6e73;--line:#dfe5ec;--blue:#007aff;--nav:#111113}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;color:var(--ink)}}.shell{{display:grid;grid-template-columns:228px minmax(0,1fr);min-height:100vh}}aside{{padding:25px 18px;background:var(--nav);color:#f5f5f7}}.brand{{font-size:19px;font-weight:750;margin-bottom:35px}}.brand small{{display:block;color:#9a9aa0;font-size:12px;font-weight:400;margin-top:5px}}.nav{{padding:12px;border-radius:8px;background:#b7ff2a;color:#111;font-weight:700;margin-bottom:10px}}.nav.dim{{background:transparent;color:#b8b8bd}}.note{{color:#92929a;font-size:12px;line-height:1.75;margin-top:32px}}main{{padding:24px 30px 42px;min-width:0}}header{{display:flex;align-items:start;justify-content:space-between;margin:6px 0 22px}}h1{{margin:0;font-size:26px}}h2{{margin:0 0 6px;font-size:21px}}p{{margin:7px 0;color:var(--muted)}}.pill{{padding:7px 10px;border:1px solid #cfe2ff;border-radius:999px;background:#edf5ff;color:#0066cc;font-size:12px}}.section{{margin-top:26px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.card{{padding:19px;border:1px solid var(--line);border-radius:8px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.025)}}.card article{{min-height:124px;padding:17px;border:1px solid var(--line);border-top:4px solid #34c759;border-radius:8px;background:#fff}}.card article span,.card article small{{display:block;color:var(--muted);font-size:13px}}.card article strong{{display:block;font-size:29px;margin:8px 0}}.overview-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}.counts{{display:flex;gap:38px;margin-top:22px}}.counts strong{{display:block;font-size:28px}}.counts small{{color:var(--muted)}}.status{{display:grid;grid-template-columns:88px 1fr 26px;gap:10px;align-items:center;margin:11px 0;font-size:13px}}.status i{{height:9px;border-radius:99px;background:#e8eef4;overflow:hidden}}.status b{{display:block;height:100%;border-radius:99px;background:#34c759}}.status:nth-child(3) b{{background:#f5a623}}.status:nth-child(4) b{{background:#e04b4b}}iframe{{display:block;width:100%;border:0;background:transparent;min-height:1200px}}@media(max-width:900px){{.shell{{grid-template-columns:1fr}}aside{{display:none}}main{{padding:18px}}.grid,.overview-grid{{grid-template-columns:1fr}}}}</style></head>
<body><div class="shell"><aside><div class="brand">运营数据分析<small>Proposal Demo · 单文件完整快照</small></div><div class="nav">Apple Insight</div><div class="nav dim">经销商 Insight</div><div class="note">此文件已内嵌 Apple 总览与完整历史报告，可直接双击打开。</div></aside><main>
<header><div><h1>运营数据分析</h1><p>Apple 经销商网络与小红书矩阵运营洞察</p></div><span class="pill">{source["fiscal_period"]} · {source["cutoff"]}</span></header>
<section class="section"><h2>Apple Insight</h2><p>FY26 KPI 网络总览</p><div class="grid">{cards}</div><div class="overview-grid"><article class="card"><h2>账号范围与质量</h2><div class="counts"><div><strong>{account_counts["core_kpi"]}</strong><small>经销商 KPI 账号</small></div><div><strong>{account_counts["expanded_store"]}</strong><small>扩展门店账号</small></div><div><strong>{report_data["summary"]["accounts"]}</strong><small>报告覆盖账号</small></div></div></article><article class="card"><h2>KPI 状态分布</h2>{status_rows}</article></div></section>
<section class="section"><iframe id="full-report" title="小红书矩阵笔记商业分析报告" srcdoc="{srcdoc}"></iframe></section>
</main></div><script>const frame=document.getElementById('full-report');function resize(){{try{{const doc=frame.contentDocument;if(doc)frame.style.height=Math.max(1200,doc.documentElement.scrollHeight,doc.body.scrollHeight)+24+'px';}}catch(_e){{}}}}frame.addEventListener('load',()=>{{resize();[200,800,1800,3500].forEach(delay=>setTimeout(resize,delay));}});</script></body></html>'''
    Path(args.output).write_text(output, encoding="utf-8")
    print(f"Built {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
