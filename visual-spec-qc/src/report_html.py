# -*- coding: utf-8 -*-
"""分眾 HTML 報告 — 業務白話視角 + 工程/設計可執行視角。純字串,無依賴。"""
import html

RESP_LABEL = {"CODE": "程式問題", "DESIGN": "設計問題",
              "NEEDS_HUMAN": "待人工確認", "PASS": "通過", "ACCEPTED": "已接受"}
RESP_COLOR = {"CODE": "#d63d38", "DESIGN": "#1f6fe0",
              "NEEDS_HUMAN": "#545667", "ACCEPTED": "#178a63"}
SEV_COLOR = {"high": "#d63d38", "medium": "#a5690f", "low": "#a06b0d",
             "info": "#545667", "pass": "#0e7a78", "accepted": "#178a63"}
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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
 /* 柔霧儀表板 · 淺灰底 × 白卡浮起 */
 :root{{--bg:#f4f6fb;--fg:#14151f;--mut:#666b7d;--line:#e3e2ec;--card:#ffffff;--card-2:#eceaf3;
   --shadow:0 10px 26px -14px rgba(40,60,140,.13),0 2px 6px rgba(40,60,140,.04);}}
 *{{box-sizing:border-box}} body{{margin:0;font-family:"Inter","Noto Sans TC",-apple-system,"Segoe UI",sans-serif;color:var(--fg);background:var(--bg);line-height:1.65}}
 .wrap{{max-width:1080px;margin:0 auto;padding:24px}}
 h1{{font-size:22px;margin:0 0 2px;font-weight:700}} .sub{{color:var(--mut);font-size:13px;margin-bottom:20px}}
 .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}}
 .kpi{{flex:1;min-width:130px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;box-shadow:var(--shadow)}}
 .kpi b{{display:block;font-size:28px;font-weight:800;letter-spacing:-.02em}} .kpi span{{color:var(--mut);font-size:12px}}
 .frame{{border:1px solid var(--line);border-radius:18px;margin-bottom:14px;overflow:hidden;background:var(--card);box-shadow:var(--shadow)}}
 .fh{{display:flex;align-items:center;gap:12px;padding:14px 16px;background:var(--card-2)}}
 .fh .name{{font-weight:700;font-size:16px}} .fh .verdict{{margin-left:auto;font-weight:700}}
 .plain{{padding:6px 16px 16px;font-size:14px;line-height:1.7;color:var(--fg)}}
 .tbl-wrap{{overflow-x:auto}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
 th{{background:var(--card-2);font-size:12px;color:var(--mut);position:sticky;top:0}}
 .pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;color:#fff;white-space:nowrap}}
 .sw{{display:inline-block;width:12px;height:12px;border-radius:4px;border:1px solid #0002;vertical-align:-2px;margin-right:4px}}
 code{{background:var(--card-2);padding:1px 5px;border-radius:6px;font-size:12px}}
 .assignee{{font-size:11px;color:var(--mut)}}
 .legend{{font-size:12px;color:var(--mut);margin:0 0 18px;line-height:1.9;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 16px;box-shadow:var(--shadow)}}
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
    acc_kpi = (f'<div class="kpi"><b style="color:#178a63">{t["ACCEPTED"]}</b>'
               f'<span>已接受(基準線)</span></div>') if t.get("ACCEPTED") else ""
    return f"""<div class="kpis">
      <div class="kpi"><b>{t['score']}%</b><span>整體還原度</span></div>
      <div class="kpi"><b style="color:#d63d38">{t['CODE']}</b><span>程式要修(前端)</span></div>
      <div class="kpi"><b style="color:#1f6fe0">{t['DESIGN']}</b><span>設計要補(設計師)</span></div>
      <div class="kpi"><b style="color:#545667">{t['NEEDS_HUMAN']}</b><span>待人工確認</span></div>
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
                      <span style="color:#666b7d">{esc(r['resp_msg'])}</span></td>
                </tr>""")
            body = f"""<div class="tbl-wrap"><table><thead><tr>
              <th>判定</th><th>元件 / 選擇器</th><th>屬性</th>
              <th>設計規格</th><th>實際渲染</th><th>差異 / 說明</th>
            </tr></thead><tbody>{''.join(trs)}</tbody></table></div>"""
        blocks.append(f"""<div class="frame">
          <div class="fh"><span class="name">{esc(f['name'])}</span>
            <span style="margin-left:auto;color:#666b7d">還原度 {f['score']}%　差異 {len(rows)} 項</span>
          </div>{body}</div>""")
    return "".join(blocks)

def _val_cell(prop, v):
    if prop in ("color", "backgroundColor", "borderColor") and str(v).startswith("#"):
        return f'<span class="sw" style="background:{esc(v)}"></span><code>{esc(v)}</code>'
    return f"<code>{esc(v)}</code>"
