#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_diff.py — 執行差異(Run Diff):比較兩輪核對,只標「動了什麼」

適用「修 → 驗 → 修」來回測試:同一份設計,程式每輪改動。
比出:
  ✅ 已解決   上輪不符、這輪通過
  🔴 新增回歸 上輪通過、這輪不符(不小心改壞的 → 最該當場抓到)
  ⏳ 仍未解決 兩輪都不符
  ➕ 新增問題 這輪新出現的節點/屬性且不符
  ⊖ 已移除   上輪有、這輪消失的問題項

用法:
  python3 run_diff.py <figma_nodes.json> <dom_prev.json> <dom_curr.json> <out.html>
"""
import json, sys
import auto_qa
from report_html import esc

FAIL = {"CODE", "DESIGN", "NEEDS_HUMAN"}
RESP = {"CODE": ("程式", "#d63d38"), "DESIGN": ("設計", "#1f6fe0"), "NEEDS_HUMAN": ("待人工", "#545667")}

def flatten(report):
    out = {}
    for f in report["frames"]:
        for r in f["rows"]:
            out[(f["name"], r["selector"], r["prop"])] = r
    return out

def diff(prev, curr):
    cats = {"RESOLVED": [], "REGRESSED": [], "STILL_OPEN": [], "NEW": [], "REMOVED": []}
    for k, c in curr.items():
        cp = c["responsibility"]; p = prev.get(k)
        if p is None:
            if cp in FAIL: cats["NEW"].append((k, None, c))
        else:
            pp = p["responsibility"]
            if pp == "PASS" and cp in FAIL:   cats["REGRESSED"].append((k, p, c))
            elif pp in FAIL and cp == "PASS": cats["RESOLVED"].append((k, p, c))
            elif pp in FAIL and cp in FAIL:   cats["STILL_OPEN"].append((k, p, c))
    for k, p in prev.items():
        if k not in curr and p["responsibility"] in FAIL:
            cats["REMOVED"].append((k, p, None))
    return cats

def run(figma, dom_prev, dom_curr, accepted=None):
    rep_prev, _, _ = auto_qa.run(figma, dom_prev, accepted)
    rep_curr, _, _ = auto_qa.run(figma, dom_curr, accepted)
    cats = diff(flatten(rep_prev), flatten(rep_curr))
    return rep_prev, rep_curr, cats

# ------------------------------------------------------------------ #
def render(rep_prev, rep_curr, cats):
    sp, sc = rep_prev["totals"]["score"], rep_curr["totals"]["score"]
    delta = sc - sp
    dcol = "#0e7a78" if delta > 0 else ("#d63d38" if delta < 0 else "#666b7d")
    darrow = "▲" if delta > 0 else ("▼" if delta < 0 else "＝")

    def rows(items, kind):
        out = []
        for (k, p, c) in items:
            frame, sel, prop = k
            key = sel.replace("[data-figma-id='", "").replace("']", "")
            node = (c or p)["node"]
            if kind == "RESOLVED":
                pr, pc = RESP[p["responsibility"]]
                detail = f'<span style="color:{pc}">{pr}</span> → <span style="color:#0e7a78">通過</span>　' \
                         f'<span class="mono">{esc(p["actual"])}</span> → <span class="mono">{esc(c["actual"])}</span>'
            elif kind == "REGRESSED":
                cr, cc = RESP[c["responsibility"]]
                detail = f'<span style="color:#0e7a78">通過</span> → <span style="color:{cc}">{cr}</span>　' \
                         f'<span class="mono">{esc(p["actual"])}</span> → <span class="mono">{esc(c["actual"])}</span>　{esc(c["detail"])}'
            elif kind == "STILL_OPEN":
                cr, cc = RESP[c["responsibility"]]
                detail = f'<span style="color:{cc}">{cr}</span>　設計 <span class="mono">{esc(c["spec"])}</span> · 實作 <span class="mono">{esc(c["actual"])}</span>　{esc(c["detail"])}'
            elif kind == "NEW":
                cr, cc = RESP[c["responsibility"]]
                detail = f'<span style="color:{cc}">{cr}</span>　{esc(c["detail"])}'
            else:  # REMOVED
                detail = "此問題項已不存在(元素/屬性移除)"
            out.append(f'<tr><td><b>{esc(node)}</b><span class="k">{esc(key)}</span></td>'
                       f'<td>{esc(prop)}</td><td>{detail}</td></tr>')
        return "".join(out)

    def block(kind, icon, title, col):
        items = cats[kind]
        if not items:
            return ""
        return f"""<div class="blk"><div class="bh" style="color:{col}">{icon} {title}
          <span class="cnt" style="background:{col}">{len(items)}</span></div>
          <table>{rows(items, kind)}</table></div>"""

    body = (block("REGRESSED", "🔴", "新增回歸(這輪改壞的)", "#d63d38")
            + block("RESOLVED", "✅", "已解決", "#0e7a78")
            + block("NEW", "➕", "新增問題", "#a5690f")
            + block("STILL_OPEN", "⏳", "仍未解決", "#666b7d")
            + block("REMOVED", "⊖", "已移除", "#9ea3b4"))
    if not body:
        body = '<div class="empty">兩輪之間沒有變化。</div>'

    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>執行差異</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#f4f6fb;--sf:#fff;--ink:#14151f;--mut:#666b7d;--line:#e3e2ec;
 --shadow:0 10px 26px -14px rgba(40,60,140,.13),0 2px 6px rgba(40,60,140,.04)}}

*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Inter","Noto Sans TC",-apple-system,"Segoe UI",sans-serif}}
.mono{{font-family:"IBM Plex Mono",monospace}}
.wrap{{max-width:860px;margin:0 auto;padding:26px 22px 60px}}
h1{{font-size:21px;margin:0 0 16px;font-weight:700}}
.delta{{display:flex;align-items:baseline;gap:14px;background:var(--sf);border:1px solid var(--line);
 border-radius:18px;padding:18px 22px;margin-bottom:22px;box-shadow:var(--shadow)}}
.delta .a{{font-family:"IBM Plex Mono",monospace;font-size:15px;color:var(--mut)}}
.delta .big{{font-size:30px;font-weight:800;letter-spacing:-.02em}}
.blk{{background:var(--sf);border:1px solid var(--line);border-radius:18px;margin-bottom:14px;overflow:hidden;box-shadow:var(--shadow)}}
.bh{{font-weight:700;font-size:15px;padding:13px 16px;display:flex;align-items:center;gap:9px}}
.cnt{{color:#fff;font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;border-radius:999px;padding:1px 9px;margin-left:auto}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
td{{padding:10px 16px;border-top:1px solid var(--line);vertical-align:top}}
td b{{font-weight:600}} .k{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--mut);display:block;margin-top:2px}}
.mono{{font-variant-numeric:tabular-nums}}
.empty{{text-align:center;color:var(--mut);padding:40px;background:var(--sf);border:1px solid var(--line);border-radius:18px}}
</style></head><body><div class="wrap">
<h1>執行差異　Round Diff</h1>
<div class="delta"><span class="a">還原度</span>
  <span class="big" style="color:var(--mut)">{sp}%</span><span class="a">→</span>
  <span class="big" style="color:{dcol}">{sc}%</span>
  <span class="big" style="color:{dcol};font-size:18px">{darrow} {abs(delta)}</span></div>
{body}
</div></body></html>"""

if __name__ == "__main__":
    args = sys.argv[1:]
    accepted = None
    if "--accepted" in args:
        i = args.index("--accepted")
        accepted = json.load(open(args[i+1], encoding="utf-8"))
        del args[i:i+2]
    if len(args) < 4:
        print(__doc__); sys.exit(1)
    figma = json.load(open(args[0], encoding="utf-8"))
    dom_prev = json.load(open(args[1], encoding="utf-8"))
    dom_curr = json.load(open(args[2], encoding="utf-8"))
    rep_prev, rep_curr, cats = run(figma, dom_prev, dom_curr, accepted)
    open(args[3], "w", encoding="utf-8").write(render(rep_prev, rep_curr, cats))
    sp, sc = rep_prev["totals"]["score"], rep_curr["totals"]["score"]
    print("=" * 56)
    print(f"執行差異  還原度 {sp}% → {sc}%  ({'+' if sc>=sp else ''}{sc-sp})")
    print("=" * 56)
    label = {"REGRESSED": "🔴 新增回歸", "RESOLVED": "✅ 已解決", "NEW": "➕ 新增問題",
             "STILL_OPEN": "⏳ 仍未解決", "REMOVED": "⊖ 已移除"}
    for kind in ("REGRESSED", "RESOLVED", "NEW", "STILL_OPEN", "REMOVED"):
        for (k, p, c) in cats[kind]:
            key = k[1].replace("[data-figma-id='", "").replace("']", "")
            print(f"  {label[kind]:10} {key} · {k[2]}")
    print("報告已輸出:", args[3])
