#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
auto_qa.py — 依「Figma 交付規範」自動對位的核對引擎

不再需要人工貼選擇器。對位規則完全來自規範卡:
  · Frame 命名  /route @width   → 推導 測試 URL + 瀏覽器寬度
  · 圖層 key    hero:title 等    ↔ DOM [data-figma-id='hero:title']
  · 同 key 自動配對,逐屬性比對;配不到的列入「覆蓋率」報告

輸入:
  figma_nodes.json  設計事實(依規範,每個節點帶 key + props{value,token})
  dom_facts.json    由 extract_dom.js 自動蒐集的 [data-figma-id] 元素 computed
輸出:
  逐屬性報告(沿用 report_html)+ 覆蓋率摘要(matched / 設計獨有 / 實作獨有)

用法: python3 auto_qa.py figma_nodes.json dom_facts.json out.html
"""
import re, json, sys
import qa_engine as qe
from report_html import render

# ------------------------------------------------------------------ #
# 1. Frame 命名解析:  "/about @1440"  ->  ("/about", 1440)
# ------------------------------------------------------------------ #
def parse_frame_name(name):
    m = re.search(r'[@＠]\s*(\d{3,4})', name or "")
    width = int(m.group(1)) if m else None
    route = re.sub(r'[@＠]\s*\d{3,4}\s*$', '', name or "").strip()
    return route, width

def make_url(base, route, explicit):
    if explicit:
        return explicit
    if not base:
        return route or ""
    # 支援 hash 路由: base 結尾 '#' + route '/about' -> '.../#/about'
    return base.rstrip('/') + (route or "") if base.endswith('#') else base.rstrip('/') + (route or "")

# ------------------------------------------------------------------ #
# 2. 依規範把設計事實展開成引擎可吃的 spec(selector = data-figma-id)
# ------------------------------------------------------------------ #
def build_plan_and_spec(figma):
    base = figma.get("baseURL", "")
    plan, spec_nodes = [], []
    for fr in figma["frames"]:
        route = fr.get("route"); width = fr.get("width")
        pr, pw = parse_frame_name(fr.get("name", ""))
        route = route if route is not None else pr
        width = width if width is not None else pw
        url = make_url(base, route, fr.get("url"))
        keys = [n["key"] for n in fr["nodes"]]
        plan.append({"frame": fr.get("name"), "route": route, "width": width,
                     "url": url, "keys": keys})
        for n in fr["nodes"]:
            spec_nodes.append({
                "frame": fr.get("name", route or "frame"),
                "name": n.get("name", n["key"]),
                "selector": f"[data-figma-id='{n['key']}']",
                "key": n["key"], "props": n["props"],
            })
    return plan, {"nodes": spec_nodes}

# ------------------------------------------------------------------ #
# 3. DOM 事實:harvester 已用 data-figma-id 蒐集;統一 selector 形式
# ------------------------------------------------------------------ #
def normalize_dom(dom):
    nodes = []
    for d in dom.get("nodes", []):
        key = d.get("key") or _key_from_selector(d.get("selector", ""))
        nodes.append({"selector": f"[data-figma-id='{key}']",
                      "key": key, "computed": d.get("computed", {})})
    return {"nodes": nodes}, {d["key"] for d in nodes if d.get("key")}

def _key_from_selector(sel):
    m = re.search(r"data-figma-id=['\"]([^'\"]+)['\"]", sel)
    return m.group(1) if m else sel

# ------------------------------------------------------------------ #
# 4. 覆蓋率:每個 frame 設計 keys vs 實作 keys
# ------------------------------------------------------------------ #
def coverage(plan, dom_keys):
    rows = []
    for p in plan:
        design = set(p["keys"])
        matched = design & dom_keys
        design_only = design - dom_keys      # 設計有、實作沒做/漏對位
        dom_only = dom_keys - design         # 實作有、設計沒定義(多餘/舊件)
        rows.append({"frame": p["frame"], "url": p["url"], "width": p["width"],
                     "matched": sorted(matched), "design_only": sorted(design_only),
                     "dom_only": sorted(dom_only)})
    return rows

# ------------------------------------------------------------------ #
def run(figma, dom):
    plan, spec = build_plan_and_spec(figma)
    dom_norm, dom_keys = normalize_dom(dom)
    report = qe.run(spec, dom_norm)
    cov = coverage(plan, dom_keys)
    return report, cov, plan

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("用法: python3 auto_qa.py <figma_nodes.json> <dom_facts.json> <out.html>")
        sys.exit(1)
    figma = json.load(open(sys.argv[1], encoding="utf-8"))
    dom = json.load(open(sys.argv[2], encoding="utf-8"))
    report, cov, plan = run(figma, dom)
    open(sys.argv[3], "w", encoding="utf-8").write(render(report))

    t = report["totals"]
    print("=" * 60)
    print("自動對位核對結果(零人工選擇器)")
    print("=" * 60)
    for p in plan:
        print(f"◆ {p['frame']}  →  {p['url'] or '(未設定URL)'} @ {p['width']}px")
    print("-" * 60)
    print(f"整體還原度 {t['score']}% | 通過 {t['pass']}/{t['checks']} | "
          f"程式 {t['CODE']} | 設計 {t['DESIGN']} | 待確認 {t['NEEDS_HUMAN']}")
    print("-" * 60)
    print("【對位覆蓋率】")
    for c in cov:
        print(f"  {c['frame']}: 配對成功 {len(c['matched'])} | "
              f"設計獨有(實作漏做) {c['design_only'] or '—'} | "
              f"實作獨有(設計未定義) {c['dom_only'] or '—'}")
    print("報告已輸出:", sys.argv[3])
