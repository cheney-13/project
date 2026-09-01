#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_section.py — 多尺寸核對(一個 section 放多 RWD 尺寸 → 一次跑出各尺寸報告 + 合併總覽)

把「同一頁的各 RWD 尺寸」當成一組批次:每個尺寸各自把瀏覽器設成該 @寬度 抓網站、
對照該尺寸的 Figma 設計事實,逐尺寸算還原度,並產出一頁合併總覽(每尺寸一張卡)。

整條鏈 = 這支工具串起來的三段:
  ① 設計事實  各尺寸 frame 的 get_design_context → figma_extract(或預抽好的 figmaNodes)
  ② 實作事實  網站在各寬度的 DOM:--live 時用 fetch_dom.py(Playwright)即時抓;否則讀既有檔
  ③ 比對產出  auto_qa(data-figma-id)/ qa_engine(CSS 選擇器)→ 分眾報告 + 合併總覽 + CI 門檻

Section 設定檔(section.json):
{
  "section": "about",
  "outDir": "out/about_multisize",
  "failUnder": 80,
  "baseURL": "https://bizdev.medialand.com.tw/demo/2021_02_MX_website/#/about",
  "selectors": "about_selectors.json",   // 選用:key→CSS 選擇器(未標 data-figma-id 的正式站,--live 用)
  "accepted": "accepted.json",           // 選用:基準線
  "sizes": [
    { "frame": "about @1440", "width": 1440, "figmaNodes": "about_1440_figma.json", "dom": "about_1440_dom.json" },
    { "frame": "about @375",  "width": 375,  "figmaContext": "about_375_ctx.txt",  "dom": "about_375_dom.json" }
  ]
}

用法:
  python3 run_section.py <section.json> [--live] [--fail-under 80]
    --live   先用 fetch_dom.py 對每個尺寸的 baseURL 即時抓 DOM(需 Playwright)再核對;
             未加則直接讀 sizes[].dom 既有檔(離線 / CI 可重現)。

也可先用 figma_section.py 從 get_metadata 產生 section 骨架,填好各尺寸的來源後再跑本工具。
"""
import os, sys, json
import qa


def _fetch_live_dom(cfg, base_dir):
    """對每個尺寸,用 fetch_dom.py 在其 @寬度 即時抓網站 DOM,寫入 sizes[].dom。"""
    import fetch_dom
    base_url = cfg.get("baseURL")
    if not base_url:
        print("--live 需要 config 的 baseURL(測試網站)"); sys.exit(2)
    selmap = None
    if cfg.get("selectors"):
        selmap = json.load(open(os.path.join(base_dir, cfg["selectors"]), encoding="utf-8"))
    for s in cfg["sizes"]:
        width = s.get("width") or 1440
        dom_path = os.path.join(base_dir, s["dom"])
        os.makedirs(os.path.dirname(dom_path) or ".", exist_ok=True)
        print(f"◆ 即時抓 DOM:{base_url} @ {width}px …")
        fetch_dom.fetch(base_url, [width], dom_path, selmap=selmap, one_file=True)


def build_qa_cfg(cfg):
    """把 section 設定轉成 qa.py 的批次 config(每尺寸 = 一組 pair)。"""
    base_url = cfg.get("baseURL", "")
    pairs = []
    for s in cfg["sizes"]:
        pair = {"name": s.get("name", s["frame"]), "frame": s["frame"],
                "url": base_url, "dom": s["dom"]}
        if s.get("figmaNodes"):
            pair["figmaNodes"] = s["figmaNodes"]
        else:
            pair["figmaContext"] = s["figmaContext"]
        if s.get("accepted"):
            pair["accepted"] = s["accepted"]
        pairs.append(pair)
    return {"outDir": cfg.get("outDir", "qa_out"),
            "failUnder": cfg.get("failUnder", 0),
            "accepted": cfg.get("accepted"),
            "pairs": pairs}


def run(cfg, base_dir, live=False, fail_under=None):
    if live:
        _fetch_live_dom(cfg, base_dir)
    qa_cfg = build_qa_cfg(cfg)
    print("=" * 64)
    print(f"多尺寸核對 · section「{cfg.get('section', '?')}」· 共 {len(cfg['sizes'])} 個尺寸")
    print("=" * 64)
    return qa.run_config_dict(qa_cfg, base_dir, fail_under)


if __name__ == "__main__":
    args = sys.argv[1:]
    live = False
    fu = None
    if "--live" in args:
        args.remove("--live"); live = True
    if "--fail-under" in args:
        i = args.index("--fail-under"); fu = int(args[i+1]); del args[i:i+2]
    if not args:
        print(__doc__); sys.exit(1)
    cfg_path = args[0]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    base_dir = os.path.dirname(os.path.abspath(cfg_path))
    sys.exit(run(cfg, base_dir, live=live, fail_under=fu))
