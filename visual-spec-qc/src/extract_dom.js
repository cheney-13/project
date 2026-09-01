/*
 * extract_dom.js — 實作事實抽取器
 * 透過 Browser MCP 的 javascript_tool 注入到目標網頁執行,
 * 回傳 { url, nodes:[{selector, computed:{...}}] },存成 dom_facts.json 餵給 qa_engine.py。
 *
 * 對位方式:優先抓帶 data-figma-id 的元素(開發時標註,最準),
 * 若專案沒有標註,可改用 SELECTORS 陣列列出要檢查的 CSS 選擇器。
 */
(function () {
  // 想比對的屬性(對應 figma_spec 的 props key)
  const PROPS = {
    color: "color",
    backgroundColor: "background-color",
    borderColor: "border-top-color",
    fontSize: "font-size",
    fontWeight: "font-weight",
    fontFamily: "font-family",
    borderRadius: "border-top-left-radius",
    gap: "gap",
    lineHeight: "line-height",
    letterSpacing: "letter-spacing",
    paddingTop: "padding-top",
    paddingRight: "padding-right",
    paddingBottom: "padding-bottom",
    paddingLeft: "padding-left",
    width: "width",
    height: "height",
  };

  // 對位模式一:自動抓所有帶 data-figma-id 的節點
  let targets = Array.from(document.querySelectorAll("[data-figma-id]"))
    .map((el) => ({ el, selector: `[data-figma-id='${el.getAttribute("data-figma-id")}']` }));

  // 對位模式二(後備):沒有 data-figma-id 時,手動列選擇器
  // const SELECTORS = [".hero-cta", ".price-tag"];
  // targets = SELECTORS.map(s => ({ el: document.querySelector(s), selector: s })).filter(t => t.el);

  const nodes = targets.map(({ el, selector }) => {
    const cs = getComputedStyle(el);
    const computed = {};
    for (const [key, cssProp] of Object.entries(PROPS)) {
      const v = cs.getPropertyValue(cssProp);
      if (v) computed[key] = v.trim();
    }
    const r = el.getBoundingClientRect();
    computed.width = Math.round(r.width) + "px";
    computed.height = Math.round(r.height) + "px";
    // key = data-figma-id 的值(規範對位鍵);沒有就退回選擇器
    const key = el.getAttribute("data-figma-id") || selector;
    return { key, selector, computed };
  });

  return { url: location.href, extractedAt: new Date().toISOString(), nodes };
})();
