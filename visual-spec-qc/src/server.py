#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — 讓「切版核對工具」真實運作的後端服務(純標準庫 http.server)

瀏覽器不能做的三件事,改由這支後端做:
  (A) 用 Figma REST 抓設計事實      figma_rest.py(需 FIGMA_TOKEN)
  (B) 用 Playwright 抓網站各寬度 DOM  fetch_dom.py(需 pip install playwright)
  (C) 跑比對引擎                     qa_engine / auto_qa
網頁(index.html)只負責顯示後端回傳的「真實結果」。

啟動:
  export FIGMA_TOKEN=figd_xxx           # Figma personal access token(唯讀即可)
  pip install playwright                # 抓網站 DOM 用(雲端環境已預裝 Chromium)
  python3 src/server.py                 # 預設 http://127.0.0.1:8787
  # 然後瀏覽器開 http://127.0.0.1:8787(工具頁與 API 同源,免 CORS)

端點:
  GET  /                 → 提供 index.html(工具頁)
  GET  /guide.html       → 提供交付規範卡
  GET  /api/health       → { figmaToken: bool, playwright: bool }
  POST /api/run          → 真實比對,body:
     { "fileKey":"nKPn…", "nodeId":"11696-7310",
       "siteUrl":"https://…/#/about",
       "selectors": { "hero:title":"section.sec-title h1" },   // 選用:未標 data-figma-id 的站
       "widths": [1440,375] }                                   // 選用:覆寫尺寸寬度
     回傳 { section, results:[{ name,width,score,status,counts,rows,coverage }] }
"""
import os, json, re
import http.server, socketserver
from urllib.parse import urlparse

import figma_rest, auto_qa, qa
from qa_engine import AcceptedIndex  # noqa: F401  (供未來擴充)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 專案根(index.html 所在)
PORT = int(os.environ.get("PORT", "8787"))

J_LABEL = {"CODE": "code", "DESIGN": "design", "NEEDS_HUMAN": "human", "ACCEPTED": "accepted"}


def _has_playwright():
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _web_rows(report):
    """把引擎報告的非通過列,轉成 index.html 明細表要的欄位。"""
    rows = []
    for f in report["frames"]:
        for r in f["rows"]:
            if r["responsibility"] in ("PASS", "ACCEPTED"):
                continue
            key = re.sub(r"^\[data-figma-id='|'\]$", "", r["selector"] or "")
            rows.append({
                "j": J_LABEL.get(r["responsibility"], "human"),
                "node": r["node"], "sel": r["selector"], "prop": r["prop"],
                "tok": r["token"] or "(未綁定)",
                "spec": r["spec"], "act": r["actual"],
                "d": r["detail"], "msg": r["resp_msg"], "key": key,
            })
    return rows


def run_real(body):
    """真實比對:Figma REST 設計事實 × 網站各寬度 DOM × 引擎。回傳可直接餵前端的結果。"""
    import fetch_dom
    token = os.environ.get("FIGMA_TOKEN")
    if not token:
        return {"error": "後端未設定 FIGMA_TOKEN(Figma access token)"}, 400
    file_key = body.get("fileKey"); node_id = body.get("nodeId")
    site_url = body.get("siteUrl")
    if not (file_key and node_id and site_url):
        return {"error": "需要 fileKey、nodeId、siteUrl"}, 400
    selectors = body.get("selectors")

    varmap = figma_rest.get_variable_names(file_key, token)
    doc = figma_rest.get_node(file_key, node_id, token)
    if doc.get("type") == "SECTION":
        sizes = figma_rest.section_size_docs(doc, varmap)
        section_name = doc.get("name")
    else:
        m = figma_rest.SIZE_RE.search(doc.get("name", ""))
        width = int(m.group(1)) if m else (body.get("widths") or [1440])[0]
        nodes = figma_rest.walk_keyed(doc, varmap, keys_only=True)
        sizes = [{"frame": doc.get("name"), "width": width, "route": None,
                  "doc": {"baseURL": "", "frames": [{"name": doc.get("name"), "nodes": nodes}]}}]
        section_name = doc.get("name")
    if not sizes:
        return {"error": "此節點下找不到名稱含 @寬度 的尺寸 frame"}, 400

    widths = body.get("widths")
    if widths:
        for s, w in zip(sizes, widths):
            s["width"] = w

    # 逐尺寸即時抓網站 DOM
    try:
        captured = {w: data for (w, data) in
                    fetch_dom.capture(site_url, [s["width"] for s in sizes], selmap=selectors)}
    except fetch_dom.PlaywrightMissing as e:
        return {"error": str(e)}, 501

    results = []
    for s in sizes:
        dom = captured[s["width"]]
        report, cov, plan = auto_qa.run(s["doc"], dom)
        t = report["totals"]
        st = qa.status_of(t["score"], t["CODE"])
        results.append({
            "name": s["frame"], "width": s["width"],
            "score": t["score"], "status": {"green": "good", "yellow": "warn", "red": "bad"}[st],
            "counts": {"code": t["CODE"], "design": t["DESIGN"],
                       "human": t["NEEDS_HUMAN"], "pass": t["pass"], "accepted": t.get("ACCEPTED", 0)},
            "rows": _web_rows(report),
            "coverage": cov[0] if cov else {},
        })
    return {"section": section_name, "results": results}, 200


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, rel, ctype):
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            return self._send(404, {"error": "not found"})
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._serve_file("index.html", "text/html; charset=utf-8")
        if p == "/guide.html":
            return self._serve_file("guide.html", "text/html; charset=utf-8")
        if p == "/api/health":
            return self._send(200, {"figmaToken": bool(os.environ.get("FIGMA_TOKEN")),
                                    "playwright": _has_playwright()})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        if p != "/api/run":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"error": f"無法解析請求:{e}"})
        try:
            payload, code = run_real(body)
        except Exception as e:
            return self._send(500, {"error": f"比對失敗:{e}"})
        return self._send(code, payload)

    def log_message(self, *a):
        pass   # 安靜


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"切版核對後端已啟動 → http://127.0.0.1:{PORT}")
        print(f"  FIGMA_TOKEN: {'已設定' if os.environ.get('FIGMA_TOKEN') else '未設定(POST /api/run 會擋)'}")
        print(f"  Playwright : {'可用' if _has_playwright() else '未安裝(pip install playwright)'}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


if __name__ == "__main__":
    main()
