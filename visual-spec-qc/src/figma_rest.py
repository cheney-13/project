#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma_rest.py — 用 Figma REST API 取「設計事實」(後端真實運作用,純標準庫 urllib)

與 figma_extract.py(解析 get_design_context 的 React/Tailwind)互補:
這支直接打 Figma REST,拿節點 JSON,轉成引擎可吃的設計事實。後端服務(server.py)
無法呼叫 session 的 Figma MCP,故走 REST(需要 Figma personal access token)。

REST(需 header  X-Figma-Token: <token>):
  GET /v1/files/{file_key}/nodes?ids={id}     取節點子樹(section / frame)

節點 → 設計事實對照:
  文字色 color        ← TEXT 的 fills[0].color
  背景色 backgroundColor ← FRAME/RECT 的 fills[0].color
  邊框色 borderColor  ← strokes[0].color
  字級/字重/字型      ← TEXT 的 style.fontSize / fontWeight / fontFamily
  圓角 borderRadius   ← cornerRadius
  間距 gap            ← itemSpacing(auto-layout)
  內距 padding*       ← paddingLeft/Right/Top/Bottom(auto-layout)
  綁定 token          ← boundVariables 內對應鍵存在即視為「有綁 token」(值放變數 id 或名稱)

token 只需「有/無」即可決定責任歸因(有綁=程式問題、hardcode=設計問題);
若另外提供 variables 名稱表(GET /v1/files/{key}/variables/local,Enterprise),則填人類可讀名稱。
"""
import json, re, sys
import urllib.request, urllib.parse

API = "https://api.figma.com/v1"


# ------------------------------------------------------------------ #
# REST 呼叫
# ------------------------------------------------------------------ #
def _get(path, token):
    req = urllib.request.Request(API + path, headers={"X-Figma-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def get_node(file_key, node_id, token):
    """取單一節點子樹的 document JSON。node_id 可為 11696-7310 或 11696:7310。"""
    nid = node_id.replace("-", ":")
    data = _get(f"/files/{file_key}/nodes?ids={urllib.parse.quote(nid)}", token)
    entry = data.get("nodes", {}).get(nid)
    if not entry:
        raise KeyError(f"節點 {nid} 不存在或無權限")
    return entry["document"]

def get_variable_names(file_key, token):
    """(選用)取 variables 名稱表 {variableId: name};非 Enterprise 會失敗,回空表。"""
    try:
        data = _get(f"/files/{file_key}/variables/local", token)
    except Exception:
        return {}
    out = {}
    for vid, v in (data.get("meta", {}).get("variables", {}) or {}).items():
        out[vid] = v.get("name", vid)
    return out


# ------------------------------------------------------------------ #
# 值轉換
# ------------------------------------------------------------------ #
def _hex(c):
    if not c:
        return None
    r, g, b = (int(round(c.get(k, 0) * 255)) for k in ("r", "g", "b"))
    return "#{:02X}{:02X}{:02X}".format(r, g, b)

def _num(v):
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else round(f, 2)

def _bound(node, key, varmap):
    """boundVariables 內有 key → 回傳 token 名稱(或變數 id);否則 None。"""
    bv = node.get("boundVariables") or {}
    ref = bv.get(key)
    if isinstance(ref, list):
        ref = ref[0] if ref else None
    if isinstance(ref, dict) and ref.get("id"):
        return varmap.get(ref["id"], ref["id"])
    return None


# ------------------------------------------------------------------ #
# 節點 → 設計事實
# ------------------------------------------------------------------ #
def node_facts(node, varmap=None):
    """單一節點 → {prop: {value, token}}。抓得到什麼算什麼(抓不到的屬性不放)。"""
    varmap = varmap or {}
    props = {}

    def put(prop, value, token):
        if value is not None:
            props[prop] = {"value": value, "token": token}

    fills = node.get("fills") or []
    solid = next((f for f in fills if f.get("type") == "SOLID" and f.get("visible", True)), None)
    if solid:
        col = _hex(solid.get("color"))
        tok = _bound(node, "fills", varmap)
        if node.get("type") == "TEXT":
            put("color", col, tok)
        else:
            put("backgroundColor", col, tok)

    strokes = node.get("strokes") or []
    stroke = next((s for s in strokes if s.get("type") == "SOLID"), None)
    if stroke:
        put("borderColor", _hex(stroke.get("color")), _bound(node, "strokes", varmap))

    style = node.get("style") or {}
    if style:
        put("fontSize", _num(style.get("fontSize")), _bound(node, "fontSize", varmap))
        put("fontWeight", _num(style.get("fontWeight")), _bound(node, "fontWeight", varmap))
        put("fontFamily", style.get("fontFamily"), _bound(node, "fontFamily", varmap))

    if node.get("cornerRadius") is not None:
        put("borderRadius", _num(node.get("cornerRadius")), _bound(node, "cornerRadius", varmap))
    if node.get("itemSpacing") is not None and node.get("layoutMode") not in (None, "NONE"):
        put("gap", _num(node.get("itemSpacing")), _bound(node, "itemSpacing", varmap))
    for side in ("Top", "Right", "Bottom", "Left"):
        key = "padding" + side
        if node.get(key) is not None:
            put(key, _num(node.get(key)), _bound(node, key, varmap))

    return props


def walk_keyed(node, varmap=None, keys_only=True):
    """走訪子樹,收集「名稱含 ':' 的具鍵節點」的設計事實(對應交付規範的 key)。"""
    varmap = varmap or {}
    out = []

    def rec(n):
        name = n.get("name", "")
        key = name if (":" in name) else None
        if key or not keys_only:
            facts = node_facts(n, varmap)
            if facts:
                out.append({"key": key or name, "name": name, "props": facts})
        for c in n.get("children", []) or []:
            rec(c)
    rec(node)
    return out


# ------------------------------------------------------------------ #
# section(多尺寸)→ 各尺寸的設計事實
# ------------------------------------------------------------------ #
SIZE_RE = re.compile(r'[@＠]\s*(\d{2,4})')

def section_size_docs(section_node, varmap=None):
    """
    吃一個 section 節點(document),回傳各尺寸的設計事實:
      [{frame, width, route, doc:{baseURL:'', frames:[{name, nodes:[...]}]}}]
    只取名稱含 @寬度 的直接子 frame(略過注記框 / popup)。
    """
    varmap = varmap or {}
    sizes = []
    for child in section_node.get("children", []) or []:
        name = (child.get("name") or "").strip()
        m = SIZE_RE.search(name)
        if not m:
            continue
        width = int(m.group(1))
        route = SIZE_RE.sub("", name).strip() or None
        nodes = walk_keyed(child, varmap, keys_only=True)
        sizes.append({"frame": name, "width": width, "route": route,
                      "doc": {"baseURL": "", "frames": [{"name": name, "nodes": nodes}]}})
    sizes.sort(key=lambda s: -s["width"])
    return sizes


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        print("用法: python3 figma_rest.py <file_key> <node_id> <token> [--out nodes.json]")
        sys.exit(1)
    file_key, node_id, token = args[0], args[1], args[2]
    out = None
    if "--out" in args:
        out = args[args.index("--out") + 1]
    varmap = get_variable_names(file_key, token)
    doc = get_node(file_key, node_id, token)
    if doc.get("type") == "SECTION":
        sizes = section_size_docs(doc, varmap)
        print(f"Section「{doc.get('name')}」找到 {len(sizes)} 個尺寸:")
        for s in sizes:
            print(f"  ◆ {s['frame']} @ {s['width']}px · {len(s['doc']['frames'][0]['nodes'])} 個具鍵節點")
        result = {"section": doc.get("name"), "sizes": sizes}
    else:
        nodes = walk_keyed(doc, varmap, keys_only=True)
        print(f"節點「{doc.get('name')}」抽出 {len(nodes)} 個具鍵節點")
        result = {"baseURL": "", "frames": [{"name": doc.get("name"), "nodes": nodes}]}
    if out:
        open(out, "w", encoding="utf-8").write(json.dumps(result, ensure_ascii=False, indent=2))
        print("已輸出 →", out)
