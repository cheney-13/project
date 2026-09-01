#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma_section.py — 從「一個 section 放多個 RWD 尺寸」的 Figma 結構,自動列出各尺寸

團隊常把同一頁的多個 RWD 尺寸並排放在一個 section 裡,例如:
  <section name="about">
    <frame name="about @1440" .../>
    <frame name="about @576"  .../>
    <frame name="about @375"  .../>
    <frame name="Frame 5448"><text name="1440以上"/></frame>   ← 注記框(略過)
    <frame name="popup" .../>                                  ← 非尺寸框(略過)
  </section>

本模組吃 Figma MCP `get_metadata` 的 XML 輸出,挑出「名稱含 @寬度」的尺寸 frame,
推導出每個尺寸的 route 與瀏覽器寬度,產出:
  · 尺寸清單(給人看 / 給 UI 的「多尺寸」用)
  · qa.py 可吃的批次 config 骨架(每個尺寸 = 一組 pair,對照網站同寬度的呈現)

只做「結構分析 / 對位規劃」,不需連網;實際抓 context/DOM 仍走 MCP 或 fetch_dom.py。

用法:
  python3 figma_section.py <metadata.xml> [--base-url https://site/#/about] [--out config.json]
"""
import re, sys, json
import xml.etree.ElementTree as ET

# @1440 / ＠576 …(全形半形皆可);2~4 位數
SIZE_RE = re.compile(r'[@＠]\s*(\d{2,4})')


def route_width(name):
    """'about @1440' → ('about', 1440);沒有 @寬度 → (route, None)。"""
    m = SIZE_RE.search(name or "")
    if not m:
        return (name or "").strip() or None, None
    width = int(m.group(1))
    route = SIZE_RE.sub('', name).strip()
    return (route or None), width


def parse_section(xml_text):
    """
    吃 get_metadata 的輸出(可含 section 前後雜訊),回傳:
      {"section": <name>, "page": <route>, "sizes": [{frame,id,route,width,figWidth}, ...]}
    只保留名稱含 @寬度 的直接子 frame(尺寸框);注記框 / popup 等自動略過。
    """
    m = re.search(r'<section\b.*?</section>', xml_text, re.S)
    section_xml = m.group(0) if m else xml_text
    root = ET.fromstring(section_xml)
    sizes = []
    for child in root:
        if child.tag != 'frame':
            continue
        name = (child.get('name') or '').strip()
        route, width = route_width(name)
        if width is None:      # 非尺寸框(注記 / popup / 裝飾)→ 略過
            continue
        fig_w = child.get('width')
        sizes.append({
            "frame": name, "id": child.get('id'),
            "route": route, "width": width,
            "figWidth": int(float(fig_w)) if fig_w else None,
        })
    sizes.sort(key=lambda s: -s["width"])   # 由大到小(桌機 → 手機)
    page = sizes[0]["route"] if sizes else None
    return {"section": root.get('name'), "page": page, "sizes": sizes}


def to_config(section, base_url="", out_dir="qa_out"):
    """把尺寸清單展開成 qa.py 批次 config 骨架(每尺寸一組 pair)。"""
    pairs = []
    for s in section["sizes"]:
        slug = re.sub(r'[^0-9A-Za-z]+', '_', f"{s['route'] or 'page'}_{s['width']}").strip('_').lower()
        pairs.append({
            "name": s["frame"],
            "frame": s["frame"],           # qa.py 依 @寬度 推導瀏覽器寬度
            "url": base_url,               # RWD 網站:同一 URL,不同視窗寬度
            "figmaContext": f"{slug}_ctx.txt",   # ← 各尺寸 frame 的 get_design_context
            "dom": f"{slug}_dom.json",           # ← 網站在該寬度的 extract_dom.js 結果
        })
    return {"_note": f"由 section「{section['section']}」自動展開的多尺寸批次;"
                     f"figmaContext/dom 待用 MCP 或 fetch_dom.py 抓取後填入。",
            "outDir": out_dir, "failUnder": 80, "pairs": pairs}


if __name__ == "__main__":
    args = sys.argv[1:]
    base_url, out = "", None
    if "--base-url" in args:
        i = args.index("--base-url"); base_url = args[i+1]; del args[i:i+2]
    if "--out" in args:
        i = args.index("--out"); out = args[i+1]; del args[i:i+2]
    if not args:
        print(__doc__); sys.exit(1)
    xml_text = open(args[0], encoding="utf-8").read()
    sec = parse_section(xml_text)
    print("=" * 60)
    print(f"Section「{sec['section']}」· 頁面 {sec['page']} · 找到 {len(sec['sizes'])} 個尺寸")
    print("=" * 60)
    for s in sec["sizes"]:
        fw = f"(畫布 {s['figWidth']}px)" if s['figWidth'] else ""
        print(f"  ◆ {s['frame']:16} → route {s['route'] or '—'} @ 瀏覽器寬 {s['width']}px {fw}")
    if out:
        cfg = to_config(sec, base_url)
        open(out, "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=2))
        print("-" * 60)
        print(f"已輸出多尺寸批次 config 骨架 → {out}(每尺寸一組 pair)")
