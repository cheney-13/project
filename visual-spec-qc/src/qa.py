#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa.py — 切版核對 CLI(單一指令跑完整條鏈)

一次批次核對多組「Figma frame ↔ 測試網頁」,產出:
  · 每組一份逐項報告  report_<slug>.html
  · 一頁總覽          index.html(還原度、燈號、覆蓋率、連到各報告)
  · 終端摘要 + CI 門檻(--fail-under)

用法:
  python3 qa.py <config.json> [--fail-under 80]

config.json:
{
  "outDir": "out/run1",
  "failUnder": 80,
  "pairs": [
    { "name": "about 桌機", "frame": "/about @1440", "url": "https://…/#/about",
      "figmaContext": "about_ctx.txt",   // get_design_context 輸出(自動抽)
      "dom": "about_dom.json" },          // extract_dom.js 蒐集結果
    { "name": "about 手機", "frame": "/about @375",
      "figmaNodes": "about_m_nodes.json", // 或直接給預抽好的設計事實
      "dom": "about_m_dom.json" }
  ]
}

【取得輸入的方式】(這條鏈的唯一整合縫)
  figmaContext ← Figma MCP get_design_context(本機 localhost:3845 / 代理人呼叫)
  dom          ← Browser MCP 注入 extract_dom.js,或 Playwright(見 fetch_dom.py)
"""
import os, re, json, sys
import figma_extract, auto_qa
from report_html import render, esc

STATUS = {"green": ("🟢", "#5e7d5a", "可上線"),
          "yellow": ("🟡", "#b98a34", "建議修正後上線"),
          "red": ("🔴", "#b4453a", "不建議上線")}

def slug(s):
    return re.sub(r'[^0-9A-Za-z]+', '_', s).strip('_').lower() or "pair"

def status_of(score, code):
    if score >= 95 and code == 0: return "green"
    return "yellow" if score >= 80 else "red"

def load_figma_doc(pair, base_dir):
    if pair.get("figmaNodes"):
        return json.load(open(os.path.join(base_dir, pair["figmaNodes"]), encoding="utf-8"))
    code = open(os.path.join(base_dir, pair["figmaContext"]), encoding="utf-8").read()
    return figma_extract.extract_doc(code, pair.get("frame", "/frame @1440"),
                                     url=pair.get("url"), keys_only=True)

def run_config(cfg_path, fail_under=None):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    return run_config_dict(cfg, base_dir, fail_under)

def run_config_dict(cfg, base_dir, fail_under=None):
    """吃已載入的 config dict(base_dir 為相對路徑基準),跑完整批次並產出報告 + 總覽。
    供 qa.py 檔案入口與 run_section.py(多尺寸)共用。"""
    out_dir = os.path.join(base_dir, cfg.get("outDir", "qa_out"))
    os.makedirs(out_dir, exist_ok=True)
    threshold = fail_under if fail_under is not None else cfg.get("failUnder", 0)

    default_accepted = cfg.get("accepted")   # 專案層級基準線(可被 pair 覆蓋)

    results = []
    for i, pair in enumerate(cfg["pairs"], 1):
        figma = load_figma_doc(pair, base_dir)
        dom = json.load(open(os.path.join(base_dir, pair["dom"]), encoding="utf-8"))
        acc_path = pair.get("accepted", default_accepted)
        accepted = json.load(open(os.path.join(base_dir, acc_path), encoding="utf-8")) if acc_path else None
        report, cov, plan = auto_qa.run(figma, dom, accepted)
        t = report["totals"]
        st = status_of(t["score"], t["CODE"])
        fname = f"report_{i:02d}_{slug(pair['name'])}.html"
        open(os.path.join(out_dir, fname), "w", encoding="utf-8").write(render(report))
        results.append({"name": pair["name"], "frame": pair.get("frame", ""),
                        "url": (plan[0]["url"] if plan else pair.get("url", "")),
                        "score": t["score"], "status": st, "totals": t,
                        "coverage": cov, "report": fname})

    idx = os.path.join(out_dir, "index.html")
    open(idx, "w", encoding="utf-8").write(render_index(cfg, results))
    print_summary(results, idx, threshold)
    worst = min((r["score"] for r in results), default=100)
    return 1 if (threshold and worst < threshold) else 0

# ------------------------------------------------------------------ #
def render_index(cfg, results):
    avg = round(sum(r["score"] for r in results) / len(results)) if results else 100
    cards = []
    for r in results:
        light, col, verdict = STATUS[r["status"]]
        t = r["totals"]
        cov = r["coverage"][0] if r["coverage"] else {"design_only": [], "dom_only": []}
        chips = []
        if t["CODE"]:  chips.append(f'<span class="chip" style="color:#b4453a;background:#f3e6e3">程式 {t["CODE"]}</span>')
        if t["DESIGN"]:chips.append(f'<span class="chip" style="color:#3f5b7a;background:#e9edf1">設計 {t["DESIGN"]}</span>')
        if t["NEEDS_HUMAN"]:chips.append(f'<span class="chip" style="color:#8f887c;background:#efece5">待確認 {t["NEEDS_HUMAN"]}</span>')
        if t.get("ACCEPTED"):chips.append(f'<span class="chip" style="color:#7c8a76;background:#eef1ea">已接受 {t["ACCEPTED"]}</span>')
        chips.append(f'<span class="chip" style="color:#5e7d5a;background:#eaefe7">通過 {t["pass"]}</span>')
        covline = ""
        if cov.get("design_only"): covline += f'<div class="cov">⚠ 實作漏做:{", ".join(esc(k) for k in cov["design_only"])}</div>'
        if cov.get("dom_only"):    covline += f'<div class="cov">＋ 設計未定義:{", ".join(esc(k) for k in cov["dom_only"])}</div>'
        cards.append(f"""<a class="card" href="{esc(r['report'])}">
          <div class="stripe" style="background:{col}"></div>
          <div class="in">
            <div class="nm">{light} {esc(r['name'])} <span class="fr">{esc(r['frame'])}</span></div>
            <div class="sl"><span class="sc" style="color:{col}">{r['score']}<small>%</small></span>
              <span class="vd" style="color:{col}">{verdict}</span></div>
            <div class="meter"><i style="width:{r['score']}%;background:{col}"></i></div>
            <div class="chips">{''.join(chips)}</div>{covline}
            <div class="go">查看逐項報告 →</div>
          </div></a>""")
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>核對總覽</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@300;400;500;700&family=Noto+Sans+TC:wght@300;400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#f4f2ec;--sf:#fff;--ink:#1f1d1a;--mut:#6f6a61;--line:#e7e3da;--ac:#c70067}}

*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);
 font-family:"Zen Kaku Gothic New","Noto Sans TC",-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:920px;margin:0 auto;padding:28px 22px 60px}}
h1{{font-size:22px;margin:0 0 2px}}.sub{{color:var(--mut);font-size:13px;margin-bottom:22px}}
.sub b{{color:var(--ink);font-family:"IBM Plex Mono",monospace}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media(max-width:600px){{.grid{{grid-template-columns:1fr}}}}
.card{{display:block;text-decoration:none;color:inherit;background:var(--sf);border:1px solid var(--line);
 border-radius:14px;overflow:hidden;transition:transform .12s}}
.card:hover{{transform:translateY(-2px)}}
.stripe{{height:5px}}.in{{padding:15px 17px}}
.nm{{font-weight:700;font-size:15px}}.fr{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--mut);
 border:1px solid var(--line);border-radius:6px;padding:1px 6px;margin-left:4px}}
.sl{{display:flex;align-items:baseline;gap:8px;margin:10px 0 4px}}
.sc{{font-family:"IBM Plex Mono",monospace;font-size:30px;font-weight:600}}.sc small{{font-size:15px}}
.vd{{font-size:12px;font-weight:600}}
.meter{{height:6px;background:var(--line);border-radius:99px;overflow:hidden;margin:6px 0 12px}}
.meter i{{display:block;height:100%}}
.chips{{display:flex;gap:6px;flex-wrap:wrap}}
.chip{{font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:99px}}
.cov{{font-size:12px;color:var(--mut);margin-top:8px}}
.go{{margin-top:11px;font-size:12px;color:var(--ac);font-weight:600}}
</style></head><body><div class="wrap">
<h1>切版核對總覽</h1>
<div class="sub">整體還原度 <b>{avg}%</b>　·　共 {len(results)} 組配對　·　點卡片看逐項明細</div>
<div class="grid">{''.join(cards)}</div>
</div></body></html>"""

def print_summary(results, idx, threshold):
    print("=" * 64)
    print("切版核對完成")
    print("=" * 64)
    for r in results:
        t = r["totals"]; light = STATUS[r["status"]][0]
        acc = f" 已接受{t['ACCEPTED']}" if t.get("ACCEPTED") else ""
        print(f"{light} {r['name']:22} {r['score']:3}%  "
              f"程式{t['CODE']} 設計{t['DESIGN']} 待確認{t['NEEDS_HUMAN']}{acc} 通過{t['pass']}/{t['checks']}")
        cov = r["coverage"][0] if r["coverage"] else {}
        if cov.get("design_only"): print(f"     ⚠ 實作漏做: {cov['design_only']}")
        if cov.get("dom_only"):    print(f"     ＋ 設計未定義: {cov['dom_only']}")
    print("-" * 64)
    print("總覽報告:", idx)
    if threshold:
        worst = min(r["score"] for r in results)
        print(f"門檻 {threshold}% → {'✅ 通過' if worst >= threshold else '❌ 未達標(最低 %d%%)' % worst}")

if __name__ == "__main__":
    args = sys.argv[1:]
    fu = None
    if "--fail-under" in args:
        i = args.index("--fail-under"); fu = int(args[i+1]); del args[i:i+2]
    if not args:
        print(__doc__); sys.exit(1)
    sys.exit(run_config(args[0], fu))
