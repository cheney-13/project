#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visual & Spec QC Agent — 核心比對引擎 (POC)

輸入:
  figma_spec.json  —— 從 Figma MCP 抽出的「設計事實」(每個節點的屬性值 + 綁定的 token)
  dom_facts.json   —— 從 Browser MCP 抽出的「實作事實」(對應 DOM 的 getComputedStyle)

輸出:
  逐屬性比對結果 + 責任歸因(設計/程式/可接受)+ 分眾 HTML 報告

純標準庫,無外部依賴。用法:
  python3 qa_engine.py <figma_spec.json> <dom_facts.json> <out.html>
"""
import json, re, sys, math, html
from datetime import datetime

# ------------------------------------------------------------------ #
# 1. 容差設定 (tolerance) — 這裡決定「多小的差異算沒錯」
# ------------------------------------------------------------------ #
TOL = {
    "color_deltaE": 2.0,   # 顏色感知差異 ΔE < 2 肉眼幾乎看不出 → 可接受
    "length_px":    1.0,   # 間距/尺寸/圓角 ±1px 內 → 可接受(子像素捨入)
    "font_size_px": 0.5,   # 字級要求較嚴
    "font_weight":  0,     # 字重需完全一致
}

# 各屬性的權重(算「還原度」時用)與嚴重度基準
WEIGHT = {
    "color": 3, "backgroundColor": 3, "borderColor": 2,
    "fontSize": 3, "fontWeight": 2, "fontFamily": 2,
    "borderRadius": 1, "gap": 2,
    "paddingTop": 1, "paddingRight": 1, "paddingBottom": 1, "paddingLeft": 1,
    "width": 1, "height": 1,
}
COLOR_PROPS  = {"color", "backgroundColor", "borderColor"}
LENGTH_PROPS = {"fontSize", "borderRadius", "gap", "width", "height", "lineHeight",
                "letterSpacing", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft"}

# ------------------------------------------------------------------ #
# 2. 值的正規化 (normalize)
# ------------------------------------------------------------------ #
def parse_color(v):
    """吃 #RGB / #RRGGBB / rgb() / rgba() → (r,g,b) 0-255,失敗回 None"""
    if v is None:
        return None
    v = str(v).strip()
    m = re.match(r'#([0-9a-fA-F]{3})$', v)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) for c in h)
    m = re.match(r'#([0-9a-fA-F]{6})$', v)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    m = re.match(r'rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)', v)
    if m:
        return tuple(int(round(float(m.group(i)))) for i in (1, 2, 3))
    return None

def _srgb_to_lab(rgb):
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x) for x in rgb)
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883
    def f(t):
        return t ** (1/3) if t > 0.008856 else 7.787 * t + 16/116
    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

def delta_e(c1, c2):
    """CIE76 ΔE — 對 POC 足夠;要更準可換 CIEDE2000"""
    l1 = _srgb_to_lab(c1); l2 = _srgb_to_lab(c2)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(l1, l2)))

def parse_len(v):
    """吃 '16px' / 16 / '16' → float px,失敗回 None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r'(-?[\d.]+)\s*(?:px)?$', str(v).strip())
    return float(m.group(1)) if m else None

def norm_family(v):
    if v is None:
        return None
    first = str(v).split(",")[0].strip().strip('"').strip("'").lower()
    return first

# ------------------------------------------------------------------ #
# 3. 單一屬性比對 → 回傳 (match, detail, actual_disp, spec_disp)
# ------------------------------------------------------------------ #
def compare_prop(prop, spec_val, dom_val):
    if prop in COLOR_PROPS:
        a, b = parse_color(spec_val), parse_color(dom_val)
        if a is None or b is None:
            return None, "無法解析顏色", str(dom_val), str(spec_val)
        d = delta_e(a, b)
        return (d <= TOL["color_deltaE"], f"ΔE={d:.1f}",
                _hex(b), _hex(a))
    if prop in LENGTH_PROPS:
        a, b = parse_len(spec_val), parse_len(dom_val)
        if a is None or b is None:
            return None, "無法解析數值", str(dom_val), str(spec_val)
        tol = TOL["font_size_px"] if prop == "fontSize" else TOL["length_px"]
        d = abs(a - b)
        return (d <= tol, f"差 {d:.1f}px", f"{b:g}px", f"{a:g}px")
    if prop == "fontWeight":
        try:
            a, b = int(spec_val), int(re.match(r'\d+', str(dom_val)).group())
        except Exception:
            return None, "無法解析字重", str(dom_val), str(spec_val)
        return (a == b, f"{b} vs {a}", str(b), str(a))
    if prop == "fontFamily":
        a, b = norm_family(spec_val), norm_family(dom_val)
        return (a == b, f"{b} vs {a}", str(dom_val), str(spec_val))
    # 其他:字串精確比對
    return (str(spec_val) == str(dom_val), "字串比對", str(dom_val), str(spec_val))

def _hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)

# ------------------------------------------------------------------ #
# 4. 責任歸因 (attribution) — 這支工具的靈魂
# ------------------------------------------------------------------ #
def attribute(match, spec_meta, dom_present):
    """
    回傳 (責任, 說明, 指派對象)
      match=True                        → 通過
      match=None (無法比對 / DOM 缺元素) → 對位/資料問題,需人工
      match=False:
        設計端有綁 token(規格明確) 但沒對到  → 程式問題(工程師)
        設計端沒綁 token(hardcode)          → 設計問題(設計師:規格未使用設計系統 token)
    """
    if match is True:
        return ("PASS", "符合規格", None)
    if match is None:
        if not dom_present:
            return ("NEEDS_HUMAN", "DOM 找不到對應元素(對位失敗或漏做)", "工程師")
        return ("NEEDS_HUMAN", "值無法解析,需人工確認", "任一方")
    token = (spec_meta or {}).get("token")
    if token:
        return ("CODE", f"設計規格明確(token: {token}),實作未對齊", "工程師")
    return ("DESIGN", "設計稿此屬性未綁定設計系統 token(hardcode),規格本身待補", "設計師")

def severity_of(prop, responsibility):
    if responsibility == "PASS":
        return "pass"
    if responsibility == "ACCEPTED":
        return "accepted"
    w = WEIGHT.get(prop, 1)
    if responsibility == "NEEDS_HUMAN":
        return "info"
    return "high" if w >= 3 else ("medium" if w >= 2 else "low")

# ------------------------------------------------------------------ #
# 4b. 接受清單 / 基準線 (accepted baseline) — Roadmap B
#     把「已人工確認、可接受」的差異靜音:不再阻擋還原度分數,
#     但仍完整列出並標記為「已接受」,每輪不再當雜訊。
# ------------------------------------------------------------------ #
def _key_from_selector(selector):
    """[data-figma-id='hero:title'] → hero:title;非此形式回傳原字串。"""
    m = re.search(r"data-figma-id=['\"]([^'\"]+)['\"]", selector or "")
    return m.group(1) if m else (selector or "")

class AcceptedIndex:
    """
    可接受差異的索引。來源可為:
      · {"accepted": [{key|selector, prop, reason?}, ...]}
      · 直接的 list[dict]
    prop 可用 "*" 代表整個節點所有屬性都豁免。
    比對時同時支援用 data-figma-id 的 key 或完整 selector 命中。
    """
    def __init__(self, data=None):
        self.entries = []
        rows = []
        if isinstance(data, dict):
            rows = data.get("accepted", [])
        elif isinstance(data, list):
            rows = data
        for e in rows or []:
            if not isinstance(e, dict):
                continue
            key = e.get("key")
            sel = e.get("selector")
            if key is None and sel is not None:
                key = _key_from_selector(sel)
            self.entries.append({
                "key": key, "selector": sel,
                "prop": e.get("prop", "*"),
                "reason": e.get("reason", "已接受(基準線)"),
            })

    def __bool__(self):
        return bool(self.entries)

    def match(self, selector, prop):
        """命中則回傳 reason 字串,否則 None。"""
        row_key = _key_from_selector(selector)
        for e in self.entries:
            if e["prop"] not in ("*", prop):
                continue
            if e["key"] is not None and e["key"] == row_key:
                return e["reason"]
            if e["selector"] is not None and e["selector"] == selector:
                return e["reason"]
        return None

# ------------------------------------------------------------------ #
# 5. 主流程
# ------------------------------------------------------------------ #
def run(figma_spec, dom_facts, accepted=None):
    acc = accepted if isinstance(accepted, AcceptedIndex) else AcceptedIndex(accepted)
    dom_by_sel = {d["selector"]: d for d in dom_facts.get("nodes", [])}
    frames = {}
    for node in figma_spec.get("nodes", []):
        frame = node.get("frame", "未分類畫面")
        frames.setdefault(frame, [])
        sel = node.get("selector")
        dom = dom_by_sel.get(sel)
        dom_present = dom is not None
        computed = (dom or {}).get("computed", {})
        for prop, meta in node.get("props", {}).items():
            spec_val = meta.get("value") if isinstance(meta, dict) else meta
            spec_meta = meta if isinstance(meta, dict) else {}
            dom_val = computed.get(prop)
            if not dom_present:
                match, detail, actual, spec_disp = None, "元素不存在", "—", str(spec_val)
            elif dom_val is None:
                # 元素在,但此屬性未被擷取 → 「未量測」,不可當成不符
                match, detail, actual, spec_disp = None, "DOM 未擷取此屬性", "—", str(spec_val)
            else:
                match, detail, actual, spec_disp = compare_prop(prop, spec_val, dom_val)
            resp, resp_msg, assignee = attribute(match, spec_meta, dom_present)
            row = {
                "node": node.get("name", sel), "selector": sel, "prop": prop,
                "spec": spec_disp, "actual": actual, "detail": detail,
                "token": spec_meta.get("token"),
                "responsibility": resp, "resp_msg": resp_msg,
                "assignee": assignee, "weight": WEIGHT.get(prop, 1),
            }
            # 基準線:非通過項若在接受清單內 → 靜音為「已接受」,不阻擋分數
            if resp != "PASS":
                reason = acc.match(sel, prop)
                if reason is not None:
                    row["orig_responsibility"] = resp
                    row["responsibility"] = "ACCEPTED"
                    row["resp_msg"] = f"已接受(基準線):{reason}"
                    row["assignee"] = "—"
            row["severity"] = severity_of(prop, row["responsibility"])
            frames[frame].append(row)
    return summarize(frames)

def summarize(frames):
    report = {"frames": [], "totals": {}}
    tot = {"checks": 0, "pass": 0, "CODE": 0, "DESIGN": 0, "NEEDS_HUMAN": 0,
           "ACCEPTED": 0, "high": 0, "medium": 0, "low": 0}
    for fname, rows in frames.items():
        w_total = sum(r["weight"] for r in rows)
        # 通過與「已接受」都不阻擋還原度分數
        w_ok    = sum(r["weight"] for r in rows
                      if r["responsibility"] in ("PASS", "ACCEPTED"))
        score   = round(100 * w_ok / w_total) if w_total else 100
        counts  = {k: 0 for k in ("CODE", "DESIGN", "NEEDS_HUMAN", "PASS", "ACCEPTED")}
        for r in rows:
            counts[r["responsibility"]] += 1
            tot["checks"] += 1
            if r["responsibility"] == "PASS":
                tot["pass"] += 1
            else:
                tot[r["responsibility"]] += 1
                if r["severity"] in ("high", "medium", "low"):
                    tot[r["severity"]] += 1
        status = "green" if score >= 95 and counts["CODE"] == 0 \
            else ("yellow" if score >= 80 else "red")
        report["frames"].append({
            "name": fname, "score": score, "status": status,
            "counts": counts, "rows": rows,
        })
    report["frames"].sort(key=lambda f: f["score"])
    tot["score"] = round(sum(f["score"] for f in report["frames"]) /
                         len(report["frames"])) if report["frames"] else 100
    report["totals"] = tot
    report["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return report

if __name__ == "__main__":
    args = sys.argv[1:]
    accepted = None
    if "--accepted" in args:
        i = args.index("--accepted")
        accepted = json.load(open(args[i+1], encoding="utf-8"))
        del args[i:i+2]
    if len(args) < 3:
        print("用法: python3 qa_engine.py <figma_spec.json> <dom_facts.json> <out.html> [--accepted accepted.json]")
        sys.exit(1)
    figma = json.load(open(args[0], encoding="utf-8"))
    dom   = json.load(open(args[1], encoding="utf-8"))
    rep   = run(figma, dom, accepted)
    from report_html import render
    open(args[2], "w", encoding="utf-8").write(render(rep))
    t = rep["totals"]
    acc = f" | 已接受 {t['ACCEPTED']}" if t.get("ACCEPTED") else ""
    print(f"整體還原度 {t['score']}% | 通過 {t['pass']}/{t['checks']} | "
          f"程式問題 {t['CODE']} | 設計問題 {t['DESIGN']} | 待確認 {t['NEEDS_HUMAN']}{acc}")
    print("報告已輸出:", args[2])
