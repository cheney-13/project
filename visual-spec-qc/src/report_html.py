# -*- coding: utf-8 -*-
"""分眾 HTML 報告 — 業務白話視角 + 工程/設計可執行視角。純字串,無依賴。"""
import html

RESP_LABEL = {"CODE": "程式問題", "DESIGN": "設計問題",
              "NEEDS_HUMAN": "待人工確認", "PASS": "通過", "ACCEPTED": "已接受"}
RESP_COLOR = {"CODE": "#b4453a", "DESIGN": "#3f5b7a",
              "NEEDS_HUMAN": "#8f887c", "ACCEPTED": "#7c8a76"}
SEV_COLOR = {"high": "#b4453a", "medium": "#b98a34", "low": "#c9a13b",
             "info": "#8f887c", "pass": "#5e7d5a", "accepted": "#7c8a76"}
STATUS_LIGHT = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
STATUS_VERDICT = {"green": "可上線", "yellow": "建議修正後上線", "red": "不建議上線"}

def esc(x):
    return html.escape(str(x if x is not None else "—"))

def render(rep):
    t = rep["totals"]
    kpis = _kpis(rep)
    dev = _dev_view(rep)
    legend = """<div class="legend">
      <b>判定與分派:</b>
      🔴 <b>程式問題</b>(前端):設計已綁 token / 有明確規格,實作未對齊。
      🔵 <b>設計問題</b>(設計師):設計稿此屬性沒綁 token(hardcode),規格待補。
      ⚪ <b>待人工</b>:DOM 找不到對應元素或屬性未量測。
      檢視維度涵蓋 <b>顏色 / 字型 / 字級字重 / 圓角</b> 與 <b>空間距離(間距 gap、內距 padding、外距 margin、寬高)</b>。
    </div>"""
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Visual & Spec QC 報告</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@300;400;500;700&family=Noto+Sans+TC:wght@300;400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
 /* 極簡日式 · 亮色 */
 :root{{--bg:#faf9f6;--fg:#1f1d1a;--mut:#6f6a61;--line:#e7e3da;--card:#f2efe8;}}
 *{{box-sizing:border-box}} body{{margin:0;font-family:"Zen Kaku Gothic New","Noto Sans TC",-apple-system,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg);line-height:1.65}}
 .wrap{{max-width:1080px;margin:0 auto;padding:24px}}
 h1{{font-size:22px;margin:0 0 2px}} .sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
 .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}}
 .kpi{{flex:1;min-width:130px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
 .kpi b{{display:block;font-size:28px}} .kpi span{{color:var(--mut);font-size:12px}}
 .frame{{border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden}}
 .fh{{display:flex;align-items:center;gap:12px;padding:14px 16px;background:var(--card)}}
 .fh .name{{font-weight:700;font-size:16px}} .fh .verdict{{margin-left:auto;font-weight:700}}
 .plain{{padding:6px 16px 16px;font-size:14px;line-height:1.7;color:#3a3630}}
 .tbl-wrap{{overflow-x:auto}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
 th{{background:var(--card);font-size:12px;color:var(--mut);position:sticky;top:0}}
 .pill{{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;color:#fff}}
 .sw{{display:inline-block;width:12px;height:12px;border-radius:3px;border:1px solid #0002;vertical-align:-2px;margin-right:4px}}
 code{{background:#f2efe8;padding:1px 5px;border-radius:4px;font-size:12px}}
 .assignee{{font-size:11px;color:var(--mut)}}
 .legend{{font-size:12px;color:var(--mut);margin:0 0 18px;line-height:1.9;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}}
</style></head><body><div class="wrap">
 <h1>Figma 設計稿 vs. 切版成品　核對報告</h1>
 <div class="sub">產生時間 {esc(rep['generated'])}　·　整體還原度 <b>{t['score']}%</b>　·　共檢查 {t['checks']} 項　·　給前端 / 設計師的逐項明細</div>
 {kpis}
 {legend}
 {dev}
</div></body></html>"""

def _kpis(rep):
    """頂部數字摘要(前端 / 設計師都看的:程式要修、設計要補)。"""
    t = rep["totals"]
    acc_kpi = (f'<div class="kpi"><b style="color:#7c8a76">{t["ACCEPTED"]}</b>'
               f'<span>已接受(基準線)</span></div>') if t.get("ACCEPTED") else ""
    return f"""<div class="kpis">
      <div class="kpi"><b>{t['score']}%</b><span>整體還原度</span></div>
      <div class="kpi"><b style="color:#b4453a">{t['CODE']}</b><span>程式要修(前端)</span></div>
      <div class="kpi"><b style="color:#3f5b7a">{t['DESIGN']}</b><span>設計要補(設計師)</span></div>
      <div class="kpi"><b style="color:#8f887c">{t['NEEDS_HUMAN']}</b><span>待人工確認</span></div>
      {acc_kpi}
    </div>"""

def _dev_view(rep):
    blocks = []
    for f in rep["frames"]:
        rows = [r for r in f["rows"] if r["responsibility"] != "PASS"]
        rows.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2,
                                 "info": 3, "accepted": 4}[r["severity"]])
        if not rows:
            body = '<div class="plain">✅ 全數通過,無差異。</div>'
        else:
            trs = []
            for r in rows:
                sc = SEV_COLOR[r["severity"]]
                resp_col = RESP_COLOR[r["responsibility"]]
                spec_cell = _val_cell(r["prop"], r["spec"])
                act_cell = _val_cell(r["prop"], r["actual"])
                tok = f'<br><code>{esc(r["token"])}</code>' if r["token"] else ""
                trs.append(f"""<tr>
                  <td><span class="pill" style="background:{resp_col}">{RESP_LABEL[r['responsibility']]}</span>
                      <div class="assignee">→ {esc(r['assignee'])}</div></td>
                  <td><b>{esc(r['node'])}</b><br><code>{esc(r['selector'])}</code></td>
                  <td>{esc(r['prop'])}{tok}</td>
                  <td>{spec_cell}</td>
                  <td>{act_cell}</td>
                  <td style="color:{sc}">{esc(r['detail'])}<br>
                      <span style="color:#6f6a61">{esc(r['resp_msg'])}</span></td>
                </tr>""")
            body = f"""<div class="tbl-wrap"><table><thead><tr>
              <th>判定</th><th>元件 / 選擇器</th><th>屬性</th>
              <th>設計規格</th><th>實際渲染</th><th>差異 / 說明</th>
            </tr></thead><tbody>{''.join(trs)}</tbody></table></div>"""
        blocks.append(f"""<div class="frame">
          <div class="fh"><span class="name">{esc(f['name'])}</span>
            <span style="margin-left:auto;color:#6f6a61">還原度 {f['score']}%　差異 {len(rows)} 項</span>
          </div>{body}</div>""")
    return "".join(blocks)

def _val_cell(prop, v):
    if prop in ("color", "backgroundColor", "borderColor") and str(v).startswith("#"):
        return f'<span class="sw" style="background:{esc(v)}"></span><code>{esc(v)}</code>'
    return f"<code>{esc(v)}</code>"
