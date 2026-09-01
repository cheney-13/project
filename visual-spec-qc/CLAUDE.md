# CLAUDE.md — 專案指南(給 Claude Code 續作)

## 這是什麼
Figma 設計稿 vs. 切版成品的自動核對工具(Visual & Spec QC)。透過 MCP 同時取得
Figma 底層 token 與網頁真實 DOM/Computed Style,**逐屬性比對**並自動歸因「設計問題 / 程式問題」,
產出分眾報告(業務白話 + 工程明細)。完整說明見 `README.md`。

## 執行環境
- **純 Python 3.8+,核心無外部依賴**(標準庫)。沒有 Node。
- `fetch_dom.py` 選用 Playwright(`pip install playwright && playwright install chromium`)。
- 產出的 HTML 用 Google Fonts 載入 Zen Kaku Gothic New(需連網;離線退回系統黑體)。

## 怎麼跑 / 怎麼驗
```bash
python3 src/qa.py samples/demo_project.json --fail-under 80      # 批次 CLI(exit≠0 表未達標)
python3 src/auto_qa.py samples/demo_figma_nodes.json samples/demo_dom_facts.json out/r.html
python3 src/run_diff.py samples/demo_figma_nodes.json \
        samples/demo_dom_facts.json samples/demo_dom_facts_v2.json out/diff.html
```
改動後的回歸檢查:上面三條都應正常產出;MX 真實案例
`python3 src/qa_engine.py samples/mx_figma_spec.json samples/mx_dom_facts.json out/mx.html`
應穩定得到 **80%**。

## 模組地圖(改動時看這裡)
- `qa_engine.py` — 比對核心。`TOL`=容差、`WEIGHT`=屬性權重、`compare_prop()`=逐屬性比、
  `attribute()`=責任歸因、`run()`=主流程。**改比對邏輯只動這支。**
- `figma_extract.py` — 解析 `get_design_context` 的 React+Tailwind。關鍵:`var(--token,值)`=有綁 token、
  原始值=hardcode;`classify()`=Tailwind class→CSS 屬性;`parse()`=把樣式併入最近的具鍵節點。
- `auto_qa.py` — 依規範自動對位:`parse_frame_name()` 解析 `/route @width`;以 `data-figma-id` 為 key 配對;
  `coverage()`=配對成功 / 設計獨有(漏做)/ 實作獨有(多餘)。
- `report_html.py` / `qa.py`(index)/ `run_diff.py` — 三種 HTML 輸出,共用視覺系統。
- `extract_dom.js` — 注入網頁蒐集 `[data-figma-id]` 的 computed(Browser MCP 或 fetch_dom.py 用)。

## 資料契約
- **figma_nodes**:`{baseURL, frames:[{name, url?, nodes:[{key, name, props:{prop:{value, token}}}]}]}`
- **dom_facts**:`{url, nodes:[{key, computed:{prop:value}}]}`(key = data-figma-id 值)
- 比對以 `(frame, [data-figma-id='key'], prop)` 為鍵。`token=None` 代表 hardcode。

## 交付規範(自動對位的前提)
- Frame 命名 `/route @width`;圖層 key ↔ 前端 `data-figma-id`;標準寬度 1440/768/375。
- 規範卡原始碼:`ui/handoff_spec.html`。

## 視覺系統(極簡日式 · 單一亮色)
所有 HTML 輸出共用同一套 token,改樣式要同步四處(`report_html.py`、`qa.py`、`run_diff.py`、`ui/*.html`):
```
和紙暖白 --bg:#f4f2ec / #faf9f6   墨色 --ink:#1f1d1a   髮絲線 --line:#e7e3da
傳統色  程式=朱紅#b4453a 設計=藍#3f5b7a 通過=苔綠#5e7d5a 警示=山吹#b98a34 待人工#8f887c
字體    Zen Kaku Gothic New(拉丁/數字) + Noto Sans TC(中文) + IBM Plex Mono(數據)
單一亮色主題(不做暗色);品牌 magenta #c70067 只做極少量點綴
```

## 已知地雷 / 設計決策
- **不可把「DOM 未擷取的屬性」當成不符**。`qa_engine.run()` 有防護:`dom_val is None` → 判「待人工/未量測」,
  不可歸成程式/設計問題(曾出過此 bug)。新增屬性比對時務必維持。
- `qa.py` 報告檔名用 `report_{序號}_{slug}`;slug 對全中文名字會退成 `pair`,靠序號保唯一。
- 顏色比對支援 hex 與 rgb()/rgba();`figma_extract` 的 token 名會把 `\/` 還原成 `/`。
- **唯一整合縫**:URL → context/dom 檔的即時抓取要透過 MCP(代理人)或 `fetch_dom.py`;
  獨立 Python 程序無法直接呼叫 session 的 MCP 工具。

## 路線圖(待做)
- B. 接受清單 / 基準線(靜音可接受差異) — 建議做成 `accepted.json` per 專案,`(key,prop)` 清單,
  引擎過濾出「阻擋分數」但仍列「已接受」。
- C. 趨勢紀錄(同頁還原度曲線) — 每輪存快照,畫 62%→…→100%。
- 擴充維度(陰影 / 狀態 / 多斷點)、設計稿自身一致性檢查。
