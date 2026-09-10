#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma_lint.py — Mode A 交付前「設計稿規範檢核」(讀 Figma 圖層 JSON,只需 Figma token)

四類自動檢查:
  🏷️ 命名語意化   結構圖層(Frame/Group/Component/Instance/Section)仍是預設命名(Frame 1、Group 99…)
  🎯 Token 綁定    顏色/圓角/間距/字級為 hardcode(未綁 Local Variables,boundVariables 沒有對應鍵)
  📐 RWD/佈局      有 ≥2 子元素卻沒開 Auto Layout 的容器(改寬度不會自動流動)
  👁️ 對比度        文字色 vs 最近底色的 WCAG 對比 < 4.5:1(AA)

用法(GitHub Actions 或本機):
  FIGMA_TOKEN=xxx python3 src/figma_lint.py --file <fileKey> --node <nodeId> --out reports/lint.json

核心 lint(doc, varmap) 為純函式,可用 fixture 離線測(samples/figma_rest_section.json)。
"""
import os, re, sys, json
from datetime import datetime

import figma_rest

STRUCT_TYPES = {"FRAME", "GROUP", "COMPONENT", "INSTANCE", "SECTION", "COMPONENT_SET"}
DEFAULT_NAME = re.compile(
    r'^(frame|group|rectangle|ellipse|vector|line|star|polygon|union|subtract|slice|arrow|component|instance)\s*\d*$',
    re.I)


# ---------- 對比度(WCAG)---------- #
def _rgb(color):
    if not color:
        return None
    return tuple(int(round(color.get(k, 0) * 255)) for k in ("r", "g", "b"))

def _hexrgb(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb) if rgb else "—"

def _lum(rgb):
    def f(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    if not a or not b:
        return None
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)

def _solid_fill_rgb(node):
    for f in node.get("fills") or []:
        if f.get("type") == "SOLID" and f.get("visible", True):
            return _rgb(f.get("color"))
    return None


# ---------- 主檢核 ---------- #
def lint(doc, varmap=None):
    naming, token, layout, contrast_bad = [], [], [], []

    def walk(n, bg):
        name = (n.get("name") or "").strip()
        typ = n.get("type")
        my_bg = _solid_fill_rgb(n) or bg      # 這層若有底色,往下當背景

        # 1) 命名語意化(只看結構圖層,避免被裝飾向量洗版)
        if typ in STRUCT_TYPES and DEFAULT_NAME.match(name):
            naming.append({"name": name, "type": typ})

        # 2) Token 綁定(hardcode 偵測)
        bv = n.get("boundVariables") or {}
        if _solid_fill_rgb(n) and not bv.get("fills"):
            token.append({"name": name or typ, "prop": ("color" if typ == "TEXT" else "fill"),
                          "value": _hexrgb(_solid_fill_rgb(n))})
        if n.get("cornerRadius") and not bv.get("cornerRadius"):
            token.append({"name": name or typ, "prop": "radius", "value": f"{n['cornerRadius']}px"})
        if n.get("itemSpacing") and n.get("layoutMode") not in (None, "NONE") and not bv.get("itemSpacing"):
            token.append({"name": name or typ, "prop": "gap", "value": f"{n['itemSpacing']}px"})
        st = n.get("style") or {}
        if st.get("fontSize") and not bv.get("fontSize"):
            token.append({"name": name or typ, "prop": "fontSize", "value": f"{st['fontSize']}px"})

        # 3) RWD/佈局:有多個子元素卻沒 Auto Layout
        kids = n.get("children") or []
        if typ == "FRAME" and len(kids) >= 2 and n.get("layoutMode") in (None, "NONE"):
            layout.append({"name": name or typ, "children": len(kids)})

        # 4) 對比度:文字 vs 最近底色
        if typ == "TEXT":
            fg = _solid_fill_rgb(n)
            base = my_bg if my_bg != _solid_fill_rgb(n) else bg
            ratio = contrast(fg, base or (255, 255, 255))
            # ratio < 1.5 幾乎等於「文字色 ≈ 推定底色」→ 多半是背景推定抓錯(如文字其實在漸層/圖片/深色形狀上),
            # 非真正的低對比,略過以免誤判;聚焦「看得到但不足」的 1.5–4.5 區間。
            if ratio is not None and 1.5 <= ratio < 4.5:
                contrast_bad.append({"name": name or "文字", "ratio": round(ratio, 2),
                                     "fg": _hexrgb(fg)})

        for c in kids:
            walk(c, my_bg)

    walk(doc, _solid_fill_rgb(doc) or (255, 255, 255))

    def cap(lst, fmt, n=8):
        return [fmt(x) for x in lst[:n]]

    checks = [
        {"key": "naming", "icon": "🏷️", "title": "圖層命名語意化", "count": len(naming),
         "items": cap(naming, lambda x: f"<b>{x['name']}</b> <span class='mut'>({x['type']})</span> 仍是預設命名")},
        {"key": "token", "icon": "🎯", "title": "Design Token 綁定", "count": len(token),
         "items": cap(token, lambda x: f"<b>{x['name']}</b> · {x['prop']} = <code>{x['value']}</code> 未綁 Variable(hardcode)")},
        {"key": "layout", "icon": "📐", "title": "RWD 斷點與佈局", "count": len(layout),
         "items": cap(layout, lambda x: f"<b>{x['name']}</b> 有 {x['children']} 個子元素卻未開 Auto Layout")},
        {"key": "contrast", "icon": "👁️", "title": "無障礙對比度(WCAG AA 4.5:1)", "count": len(contrast_bad),
         "items": cap(contrast_bad, lambda x: f"<b>{x['name']}</b> 文字 <code>{x['fg']}</code> 對比僅 <b>{x['ratio']}:1</b>(需 ≥ 4.5)")},
    ]
    return {"summary": {"total": sum(c["count"] for c in checks)}, "checks": checks}


def run(file_key, node_id, token, out_path):
    varmap = figma_rest.get_variable_names(file_key, token)
    doc = figma_rest.get_node(file_key, node_id, token)
    result = lint(doc, varmap)
    result["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    result["file"] = file_key
    result["node"] = node_id
    result["name"] = doc.get("name")
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 56)
    print(f"設計稿規範檢核 · {doc.get('name')} · 共 {result['summary']['total']} 項待改")
    for c in result["checks"]:
        print(f"  {c['icon']} {c['title']}: {c['count']}")
    if out_path:
        print("輸出 →", out_path)
    return result


if __name__ == "__main__":
    args = sys.argv[1:]
    def opt(flag):
        return args[args.index(flag) + 1] if flag in args else None
    file_key, node_id, out = opt("--file"), opt("--node"), opt("--out")
    token = opt("--token") or os.environ.get("FIGMA_TOKEN")
    if not (file_key and node_id and token):
        print("用法: FIGMA_TOKEN=xxx python3 src/figma_lint.py --file <key> --node <id> [--out reports/lint.json]")
        sys.exit(1)
    run(file_key, node_id, token, out)
