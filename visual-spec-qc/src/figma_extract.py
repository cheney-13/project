#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma_extract.py — 從 Figma MCP get_design_context 的輸出自動抽「設計事實」

get_design_context 回傳 React + Tailwind 代碼,其中:
  · 綁定 Figma 變數的屬性 → `xxx-[var(--<token>,<fallback>)]`  (帶 token)
  · 未綁定(hardcode)       → `xxx-[<value>]` 或具名類(bg-white 等)  (token=None)
  · 每個節點帶 data-name / data-node-id

本模組把它解析成 auto_qa.py 可吃的 figma_nodes 格式:
  {key, name, props:{prop:{value, token}}}

用法:
  python3 figma_extract.py <design_context.txt> <out.json> [--frame "/about @1440"] [--keys-only]
    --keys-only  只保留 data-name 含 ':' 的節點(符合交付規範的 key)
"""
import re, json, sys

# ------------------------------------------------------------------ #
# Tailwind class → CSS 屬性 對照
# ------------------------------------------------------------------ #
NAMED_COLOR = {"white": "#FFFFFF", "black": "#000000", "transparent": "transparent"}
NAMED_WEIGHT = {"thin": 100, "extralight": 200, "light": 300, "normal": 400,
                "medium": 500, "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}

def unwrap(raw):
    """`var(--token,fallback)` → (fallback, token);否則 (raw, None)。token 內 \\/ 還原為 /"""
    raw = raw.strip()
    m = re.match(r'var\(\s*--(.+?)\s*,\s*(.+?)\s*\)$', raw)
    if m:
        token = m.group(1).replace('\\/', '/').replace('\\', '')
        return m.group(2).strip(), token
    return raw, None

def as_len(v):
    m = re.match(r'(-?[\d.]+)\s*px$', v.strip())
    if m:
        f = float(m.group(1)); return int(f) if f.is_integer() else f
    return v

def looks_color(v):
    return bool(re.match(r'#[0-9a-fA-F]{3,8}$|rgba?\(', v.strip()))

def classify(cls):
    """回傳 (prop, rawValue) 或 None。rawValue 可能含 var(...)"""
    # 具名
    if cls in ("font-bold","font-normal","font-medium","font-semibold","font-light",
               "font-thin","font-extralight","font-extrabold","font-black"):
        return ("fontWeight", str(NAMED_WEIGHT[cls[5:]]))
    m = re.match(r'^bg-(white|black|transparent)$', cls)
    if m: return ("backgroundColor", NAMED_COLOR[m.group(1)])
    m = re.match(r'^text-(white|black|transparent)$', cls)
    if m: return ("color", NAMED_COLOR[m.group(1)])
    # 任意值 xxx-[...]
    m = re.match(r'^([a-z]+)-\[(.+)\]$', cls)
    if not m: return None
    pfx, val = m.group(1), m.group(2)
    inner,_ = unwrap(val)
    table = {"rounded":"borderRadius","gap":"gap","leading":"lineHeight","tracking":"letterSpacing",
             "pt":"paddingTop","pr":"paddingRight","pb":"paddingBottom","pl":"paddingLeft",
             "mt":"marginTop","mr":"marginRight","mb":"marginBottom","ml":"marginLeft"}
    if pfx == "bg":   return ("backgroundColor", val)
    if pfx == "text": return ("color" if looks_color(inner) else "fontSize", val)
    if pfx == "font": return ("fontWeight", val)
    if pfx in table:  return (table[pfx], val)
    return None

COLOR_PROPS = {"color","backgroundColor","borderColor"}
LEN_PROPS = {"fontSize","borderRadius","gap","lineHeight","letterSpacing",
             "paddingTop","paddingRight","paddingBottom","paddingLeft",
             "marginTop","marginRight","marginBottom","marginLeft"}

def to_prop(prop, raw):
    val, token = unwrap(raw)
    if prop in LEN_PROPS: val = as_len(val)
    elif prop == "fontWeight":
        try: val = int(val)
        except: pass
    return prop, {"value": val, "token": token}

# ------------------------------------------------------------------ #
# 解析:走訪每個標籤,把樣式併入「最近的具鍵節點」
# ------------------------------------------------------------------ #
TAG = re.compile(r'<(?:div|img|span|p|h[1-6]|button|a|section)\b([^>]*?)/?>', re.I)
def attr(tagbody, name):
    m = re.search(name + r'=[\'"]([^\'"]*)[\'"]', tagbody)
    return m.group(1) if m else None

def parse(code, keys_only=False):
    nodes, cur = [], None
    for m in TAG.finditer(code):
        body = m.group(1)
        name = attr(body, "data-name")
        nid  = attr(body, "data-node-id")
        cls  = (attr(body, "className") or "").split()
        key  = name or nid
        if key:  # 具鍵標籤 → 開新節點
            cur = {"key": name if name else nid, "name": name or nid, "_props": {}}
            nodes.append(cur)
        if cur is None:
            continue
        for c in cls:
            r = classify(c)
            if not r: continue
            prop, raw = r
            if prop in cur["_props"]:  # 同屬性保留最外層(先出現者)
                continue
            p, meta = to_prop(prop, raw)
            cur["_props"][p] = meta
    out = []
    for n in nodes:
        if not n["_props"]:      # 純結構、無樣式 → 略
            continue
        if keys_only and ":" not in n["key"]:
            continue
        out.append({"key": n["key"], "name": n["name"], "props": n["_props"]})
    return out

def extract_doc(code, frame="/frame @1440", url=None, keys_only=True):
    """context 代碼字串 → auto_qa 可吃的 figma doc"""
    fr = {"name": frame, "nodes": parse(code, keys_only)}
    if url:
        fr["url"] = url
    return {"baseURL": "", "frames": [fr]}

if __name__ == "__main__":
    args = sys.argv[1:]
    keys_only = "--keys-only" in args; args = [a for a in args if a != "--keys-only"]
    frame = "/frame @1440"
    if "--frame" in args:
        i = args.index("--frame"); frame = args[i+1]; del args[i:i+2]
    src, out = args[0], args[1]
    code = open(src, encoding="utf-8").read()
    nodes = parse(code, keys_only)
    doc = {"baseURL": "", "frames": [{"name": frame, "nodes": nodes}]}
    open(out, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False, indent=2))
    print(f"抽出 {len(nodes)} 個節點 → {out}")
    for n in nodes:
        props = ", ".join(f"{k}={v['value']}" + (f"·{v['token']}" if v['token'] else "·(hardcode)")
                          for k, v in n["props"].items())
        print(f"  ◆ {n['key']}: {props}")
