#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_dom.py —(選用)用 Playwright 自動抓 live 網站的 DOM 事實

把指定 URL 在指定寬度載入,注入 extract_dom.js 的邏輯,蒐集所有 [data-figma-id]
元素的 computed style,輸出成 auto_qa / qa.py 可吃的 dom_facts.json。

這是「無 MCP、純獨立」的 DOM 抓取路徑(Browser MCP 的替代)。需要:
  pip install playwright && playwright install chromium

用法:
  python3 fetch_dom.py <url> <out.json> [--width 1440]
"""
import json, sys, os

PROPS = {
    "color": "color", "backgroundColor": "background-color", "borderColor": "border-top-color",
    "fontSize": "font-size", "fontWeight": "font-weight", "fontFamily": "font-family",
    "borderRadius": "border-top-left-radius", "gap": "gap",
    "lineHeight": "line-height", "letterSpacing": "letter-spacing", "paddingTop": "padding-top",
}

JS = """
(() => {
  const PROPS = %s;
  const nodes = Array.from(document.querySelectorAll('[data-figma-id]')).map(el => {
    const cs = getComputedStyle(el), computed = {};
    for (const [k, p] of Object.entries(PROPS)) { const v = cs.getPropertyValue(p); if (v) computed[k] = v.trim(); }
    return { key: el.getAttribute('data-figma-id'), computed };
  });
  return { url: location.href, nodes };
})()
""" % json.dumps(PROPS)

def fetch(url, width, out):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("需要 Playwright:  pip install playwright && playwright install chromium")
        sys.exit(2)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(url, wait_until="networkidle")
        data = page.evaluate(JS)
        browser.close()
    data["width"] = width
    open(out, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"抓到 {len(data['nodes'])} 個 [data-figma-id] 節點 @ {width}px → {out}")

if __name__ == "__main__":
    args = sys.argv[1:]
    width = 1440
    if "--width" in args:
        i = args.index("--width"); width = int(args[i+1]); del args[i:i+2]
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    fetch(args[0], width, args[1])
