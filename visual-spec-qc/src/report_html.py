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
    biz = _biz_view(rep)
    dev = _dev_view(rep)
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
 .tabs{{display:flex;gap:8px;border-bottom:2px solid var(--line);margin-bottom:20px}}
 .tab{{padding:10px 18px;cursor:pointer;border:none;background:none;font-size:15px;font-weight:600;color:var(--mut);border-bottom:2px solid transparent;margin-bottom:-2px}}
 .tab.on{{color:#3f5b7a;border-bottom-color:#3f5b7a}}
 .view{{display:none}} .view.on{{display:block}}
 .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
 .kpi{{flex:1;min-width:130px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
 .kpi b{{display:block;font-size:28px}} .kpi span{{color:var(--mut);font-size:12px}}
 .frame{{border:1px solid var(--line);border-radius:12px;margin-bottom:14px;overflow:hidden}}
 .fh{{display:flex;align-items:center;gap:12px;padding:14px 16px;background:var(--card)}}
 .fh .name{{font-weight:700;font-size:16px}} .fh .verdict{{margin-left:auto;font-weight:700}}
 .bar{{height:8px;background:#eae7df;border-radius:99px;overflow:hidden;flex:1;max-width:180px}}
 .bar i{{display:block;height:100%}}
 .plain{{padding:6px 16px 16px;font-size:14px;line-height:1.7;color:#3a3630}}
 .plain li{{margin:2px 0}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
 th{{background:var(--card);font-size:12px;color:var(--mut);position:sticky;top:0}}
 .pill{{display:inline-block;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:700;color:#fff}}
 .sw{{display:inline-block;width:12px;height:12px;border-radius:3px;border:1px solid #0002;vertical-align:-2px;margin-right:4px}}
 code{{background:#f2efe8;padding:1px 5px;border-radius:4px;font-size:12px}}
 .assignee{{font-size:11px;color:var(--mut)}}
 .legend{{font-size:12px;color:var(--mut);margin:14px 0;line-height:1.8}}
</style></head><body><div class="wrap">
 <h1>Figma 設計稿 vs. 切版成品　核對報告</h1>
 <div class="sub">產生時間 {esc(rep['generated'])}　·　整體還原度 <b>{t['score']}%</b>　·　共檢查 {t['checks']} 項</div>
 <div class="tabs">
   <button class="tab on" onclick="sw(0)">👔 業務摘要</button>
   <button class="tab" onclick="sw(1)">🛠 工程 / 設計明細</button>
 </div>
 <div class="view on" id="v0">{biz}</div>
 <div class="view" id="v1">{dev}</div>
</div>
<script>
 function sw(i){{document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('on',j==i));
 document.querySelectorAll('.view').forEach((v,j)=>v.classList.toggle('on',j==i));}}
</script></body></html>"""

def _biz_view(rep):
    t = rep["totals"]
    acc_kpi = (f'<div class="kpi"><b style="color:#7c8a76">{t["ACCEPTED"]}</b>'
               f'<span>已接受(基準線)</span></div>') if t.get("ACCEPTED") else ""
    kpis = f"""<div class="kpis">
      <div class="kpi"><b>{t['score']}%</b><span>整體還原度</span></div>
      <div class="kpi"><b style="color:#b4453a">{t['CODE']}</b><span>程式要修(前端)</span></div>
      <div class="kpi"><b style="color:#3f5b7a">{t['DESIGN']}</b><span>設計要補(設計師)</span></div>
      <div class="kpi"><b style="color:#8f887c">{t['NEEDS_HUMAN']}</b><span>待人工確認</span></div>
      {acc_kpi}
    </div>"""
    cards = []
    for f in rep["frames"]:
        c = f["counts"]
        col = {"green": "#5e7d5a", "yellow": "#b98a34", "red": "#b4453a"}[f["status"]]
        bullets = []
        if c["CODE"]:
            bullets.append(f"<li>🔴 <b>{c['CODE']} 項</b>屬「程式沒照設計做」→ 已標記給 <b>前端工程師</b></li>")
        if c["DESIGN"]:
            bullets.append(f"<li>🔵 <b>{c['DESIGN']} 項</b>屬「設計稿規格未定義清楚」→ 已標記給 <b>設計師</b></li>")
        if c["NEEDS_HUMAN"]:
            bullets.append(f"<li>⚪ <b>{c['NEEDS_HUMAN']} 項</b>需人工確認(可能是對位或環境差異)</li>")
        if c.get("ACCEPTED"):
            bullets.append(f"<li>🟢 <b>{c['ACCEPTED']} 項</b>為已核准的可接受差異(基準線),不影響上線判定</li>")
        if not bullets:
            bullets.append("<li>✅ 沒有發現需處理的差異,與設計稿一致</li>")
        cards.append(f"""<div class="frame">
          <div class="fh">
            <span class="name">{STATUS_LIGHT[f['status']]} {esc(f['name'])}</span>
            <div class="bar"><i style="width:{f['score']}%;background:{col}"></i></div>
            <span style="color:{col};font-weight:700">{f['score']}%</span>
            <span class="verdict" style="color:{col}">{STATUS_VERDICT[f['status']]}</span>
          </div>
          <ul class="plain">{''.join(bullets)}</ul>
        </div>""")
    note = """<div class="legend">
      <b>怎麼看這份報告:</b>還原度是「這一頁跟設計稿的吻合程度」。
      🟢 95%↑ 且無程式問題 = 可上線;🟡 80–95% = 修一修再上;🔴 80% 以下 = 先別給客戶看。
      每項差異都已自動判斷是「設計的事」還是「程式的事」並分派好,不需要你懂技術。
    </div>"""
    return kpis + "".join(cards) + note

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
            body = f"""<table><thead><tr>
              <th>判定</th><th>元件 / 選擇器</th><th>屬性</th>
              <th>設計規格</th><th>實際渲染</th><th>差異 / 說明</th>
            </tr></thead><tbody>{''.join(trs)}</tbody></table>"""
        blocks.append(f"""<div class="frame">
          <div class="fh"><span class="name">{esc(f['name'])}</span>
            <span style="margin-left:auto;color:#6f6a61">還原度 {f['score']}%　差異 {len(rows)} 項</span>
          </div>{body}</div>""")
    return "".join(blocks)

def _val_cell(prop, v):
    if prop in ("color", "backgroundColor", "borderColor") and str(v).startswith("#"):
        return f'<span class="sw" style="background:{esc(v)}"></span><code>{esc(v)}</code>'
    return f"<code>{esc(v)}</code>"
