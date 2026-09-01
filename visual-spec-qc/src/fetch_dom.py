#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_dom.py —(即時抓取)用 Playwright 把 live 網站在指定寬度載入,抓 DOM 事實

這是「無 MCP、純獨立」的 DOM 抓取路徑(Browser MCP 的替代)。需要:
  pip install playwright && playwright install chromium
(本專案的雲端環境已預裝 Chromium;只需 pip install playwright。)

對位兩種模式:
  · 預設:抓所有帶 [data-figma-id] 的元素(開發時標註,最準)。
  · --selectors selmap.json:給「key → CSS 選擇器」對照(適用未標註 data-figma-id 的正式站),
    例如真實 MX 站用 section.sec-title h1.d-none.d-lg-block 這類選擇器對位。

多尺寸(核心):一次載入多個寬度,各輸出一份 dom_facts:
  python3 fetch_dom.py <url> <out.json> --widths 1440,768,375
    → 產出 out_1440.json / out_768.json / out_375.json(回報清單)
單一寬度(相容舊用法):
  python3 fetch_dom.py <url> <out.json> [--width 1440] [--selectors selmap.json]
"""
import json, sys, os

# 與 extract_dom.js 對齊的屬性集
PROPS = {
    "color": "color", "backgroundColor": "background-color", "borderColor": "border-top-color",
    "fontSize": "font-size", "fontWeight": "font-weight", "fontFamily": "font-family",
    "borderRadius": "border-top-left-radius", "gap": "gap",
    "lineHeight": "line-height", "letterSpacing": "letter-spacing",
    "paddingTop": "padding-top", "paddingRight": "padding-right",
    "paddingBottom": "padding-bottom", "paddingLeft": "padding-left",
}

# selmap 為 None → 抓 [data-figma-id];否則抓 selmap 指定的每個選擇器
JS = """
(({PROPS, SELMAP}) => {
  const read = (el) => {
    const cs = getComputedStyle(el), computed = {};
    for (const [k, p] of Object.entries(PROPS)) { const v = cs.getPropertyValue(p); if (v) computed[k] = v.trim(); }
    const r = el.getBoundingClientRect();
    computed.width = Math.round(r.width) + 'px';
    computed.height = Math.round(r.height) + 'px';
    return computed;
  };
  let nodes = [];
  if (SELMAP) {
    for (const [key, sel] of Object.entries(SELMAP)) {
      const el = document.querySelector(sel);
      if (el) nodes.push({ key, selector: sel, computed: read(el) });
    }
  } else {
    nodes = Array.from(document.querySelectorAll('[data-figma-id]')).map(el => {
      const key = el.getAttribute('data-figma-id');
      return { key, selector: `[data-figma-id='${key}']`, computed: read(el) };
    });
  }
  return { url: location.href, extractedAt: new Date().toISOString(), nodes };
})
"""

def _size_out(out, width):
    root, ext = os.path.splitext(out)
    return f"{root}_{width}{ext or '.json'}"

def fetch(url, widths, out, selmap=None, one_file=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("需要 Playwright:  pip install playwright"
              "(本專案雲端環境已預裝 Chromium,無需 playwright install)")
        sys.exit(2)
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in widths:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(url, wait_until="networkidle")
            data = page.evaluate(JS, {"PROPS": PROPS, "SELMAP": selmap})
            page.close()
            data["width"] = width
            target = out if one_file else _size_out(out, width)
            open(target, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
            written.append((width, target, len(data["nodes"])))
        browser.close()
    for width, target, n in written:
        print(f"抓到 {n} 個節點 @ {width}px → {target}")
    return written

if __name__ == "__main__":
    args = sys.argv[1:]
    widths, selmap = None, None
    if "--widths" in args:
        i = args.index("--widths"); widths = [int(w) for w in args[i+1].split(",") if w.strip()]; del args[i:i+2]
    if "--width" in args:
        i = args.index("--width"); widths = [int(args[i+1])]; del args[i:i+2]
    if "--selectors" in args:
        i = args.index("--selectors"); selmap = json.load(open(args[i+1], encoding="utf-8")); del args[i:i+2]
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    url, out = args[0], args[1]
    if widths is None:
        widths = [1440]
    # 單一寬度沿用原輸出檔名;多寬度各自加 _<width> 後綴
    fetch(url, widths, out, selmap=selmap, one_file=(len(widths) == 1))
