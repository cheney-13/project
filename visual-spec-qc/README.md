# Visual & Spec QC Agent

**Figma 設計稿 vs. 切版成品的自動核對工具。**

不是比像素,而是透過 MCP 同時取得 Figma 的底層 token/結構與網頁的真實
DOM/Computed Style,**逐屬性語意對位**,並自動判斷每個差異是**設計問題**還是**程式問題**,
輸出給工程/設計看的明細與給業務看的白話摘要。

---

## 為什麼這樣做

傳統「截圖比像素」抗噪差、只知道哪裡不同、不知道差多少與誰的責任。
本工具比對的是「同一元素同一屬性的**設計值 vs 實作值**」:

| 來源 | 取得方式 | 拿到的事實 |
|------|---------|-----------|
| Figma(設計意圖) | `get_design_context` / `get_variable_defs` | token 綁定、色/字/間距/圓角的值 |
| 網頁(實作成品) | 注入 `extract_dom.js` 取 `getComputedStyle` | 真實 DOM 的 computed 值 |

顏色用 **ΔE** 容差抗噪、間距帶容差、每個差異自動歸因並分派人員。

---

## 快速開始

無外部依賴,Python 3.8+ 即可(核心引擎純標準庫)。

```bash
# 1) 批次核對(單一指令跑完 → 每組報告 + 總覽 index + CI 門檻)
python3 src/qa.py samples/demo_project.json --fail-under 80

# 2) 執行差異(修 → 驗 → 修:同一設計、兩輪 DOM,只標「動了什麼」)
python3 src/run_diff.py samples/demo_figma_nodes.json \
        samples/demo_dom_facts.json samples/demo_dom_facts_v2.json out/diff.html

# 3) 單頁核對(手動指定設計事實 + DOM 事實)
python3 src/auto_qa.py samples/demo_figma_nodes.json samples/demo_dom_facts.json out/report.html
```

互動原型與規範卡(可直接用瀏覽器開):
- `ui/qa_console.html` — 切版核對台(貼連結 → 一鍵批次 → 分眾報告)
- `ui/handoff_spec.html` — Figma 交付規範卡(設計師照著整理檔案)

---

## 資料流

```
① 設計事實   Figma MCP get_design_context ──► figma_extract.py ──► figma_nodes.json
                                              (var(--token,值) 自動判定綁定)
② 實作事實   Browser MCP 注入 extract_dom.js  ──► dom_facts.json
             (或 fetch_dom.py 用 Playwright,無 MCP)
③ 對位比對   auto_qa.py:frame 命名 /route @width → URL+寬度;data-figma-id 自動配對
             qa_engine.py:逐屬性比 + 責任歸因(程式/設計/待人工/通過)
④ 產出       report_html.py(分眾報告) · qa.py(總覽) · run_diff.py(執行差異)
```

**責任歸因規則(核心)**

| 情況 | 判定 | 指派 |
|------|------|------|
| 值相符(容差內) | ✅ 通過 | — |
| 設計端**有綁 token**、實作值不符 | 🔴 程式問題 | 前端 |
| 設計端**沒綁 token**(hardcode)、值不符 | 🔵 設計問題 | 設計師(規格待補) |
| DOM 找不到對應元素 / 屬性未擷取 | ⚪ 待人工 | 對位失敗或漏做 |

容差:顏色 ΔE < 2、間距/圓角 ±1px、字級 ±0.5px、字重需完全一致(見 `qa_engine.py` 頂部 `TOL`)。

---

## 檔案結構

```
visual-spec-qc/
├── README.md
├── CLAUDE.md              # 給 Claude Code 續作的專案指南
├── LICENSE
├── src/
│   ├── qa.py             # CLI 入口:批次 + 總覽 index + CI 門檻
│   ├── qa_engine.py      # 比對 + 責任歸因 + 分數(純標準庫)
│   ├── report_html.py    # 分眾報告(業務摘要 / 工程明細)
│   ├── auto_qa.py        # 依交付規範自動對位 + 覆蓋率
│   ├── figma_extract.py  # 從 get_design_context 抽設計事實(含 token 綁定)
│   ├── run_diff.py       # 執行差異(解決/回歸/未解決)
│   ├── extract_dom.js    # 注入網頁蒐集 [data-figma-id] 的 computed
│   └── fetch_dom.py      # (選用)Playwright 抓 DOM,無需 MCP
├── ui/
│   ├── qa_console.html   # 互動原型:切版核對台
│   └── handoff_spec.html # Figma 交付規範卡
└── samples/              # 示範資料(含真實 MX 案例與規範示範)
```

---

## 交付規範(讓核對可自動化)

自動對位需要設計檔遵循約定,詳見 `ui/handoff_spec.html`:

1. **Frame 命名** `/route @width`(如 `/about @1440`)→ 工具推導測試 URL + 瀏覽器寬度。
2. **單元 key** ↔ 前端 `data-figma-id`(如圖層 `sec:hero` ↔ `data-figma-id="sec:hero"`)。
3. 標準三寬度 `1440 / 768 / 375`;交付與草稿分開;顏色/間距/字級盡量綁 Variable。

---

## 現況與路線圖

**已完成**
- 核心比對引擎 + 責任歸因 + 分眾報告
- 依規範自動對位(零人工選擇器)+ 覆蓋率(漏做 / 多餘)
- 從 `get_design_context` 自動抽設計事實(含 token 綁定)
- 單一 CLI(批次 + 總覽 + CI 門檻)
- 執行差異 A(修→驗→修:解決 / 回歸 / 未解決)
- 視覺:極簡日式亮色主題

**待做**
- B. 接受清單 / 基準線(把可接受差異靜音,每輪不再當雜訊)
- C. 趨勢紀錄(同一頁還原度曲線)
- 擴充比對維度(陰影、狀態 hover/disabled、多斷點)
- 設計稿自身一致性檢查(同 token 跨節點值不一致)

**唯一整合縫**
`qa.py` 吃的是**已抓好的** context / dom 檔。把 URL 變成這兩個檔的即時抓取:
- Figma 側 ← `get_design_context`(本機 Figma MCP,或 Figma REST API + token)
- DOM 側 ← Browser MCP 注入 `extract_dom.js`,或 `fetch_dom.py`(Playwright,已附)

---

## 授權

見 `LICENSE`(預設 MIT,可依團隊需要調整)。
