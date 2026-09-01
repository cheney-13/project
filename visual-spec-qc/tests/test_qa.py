#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visual & Spec QC — 回歸測試(純標準庫 unittest,無外部依賴)

跑法:
  python3 -m unittest discover -s tests            # 從專案根目錄
  python3 tests/test_qa.py                          # 直接跑

覆蓋:值正規化 / 逐屬性比對 / 責任歸因 / 主流程 / 覆蓋率 /
      figma_extract 的 token 綁定判定 / run_diff 分類 / 接受清單(基準線)/
      MX 真實案例還原度鎖定在 80%。
"""
import os
import sys
import json
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
SAMPLES = os.path.join(ROOT, "samples")
sys.path.insert(0, SRC)

import qa_engine as qe          # noqa: E402
import auto_qa                  # noqa: E402
import figma_extract as fx      # noqa: E402
import run_diff                 # noqa: E402


def load(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ #
class TestNormalize(unittest.TestCase):
    def test_parse_color_forms(self):
        self.assertEqual(qe.parse_color("#fff"), (255, 255, 255))
        self.assertEqual(qe.parse_color("#000000"), (0, 0, 0))
        self.assertEqual(qe.parse_color("rgb(33, 37, 41)"), (33, 37, 41))
        self.assertEqual(qe.parse_color("rgba(66,133,244,0.5)"), (66, 133, 244))
        self.assertIsNone(qe.parse_color("not-a-color"))
        self.assertIsNone(qe.parse_color(None))

    def test_delta_e_identical_is_zero(self):
        self.assertAlmostEqual(qe.delta_e((10, 20, 30), (10, 20, 30)), 0.0, places=6)

    def test_delta_e_symmetric(self):
        a, b = (10, 20, 30), (40, 50, 60)
        self.assertAlmostEqual(qe.delta_e(a, b), qe.delta_e(b, a), places=6)

    def test_parse_len(self):
        self.assertEqual(qe.parse_len("16px"), 16.0)
        self.assertEqual(qe.parse_len("16"), 16.0)
        self.assertEqual(qe.parse_len(16), 16.0)
        self.assertIsNone(qe.parse_len("auto"))
        self.assertIsNone(qe.parse_len(None))

    def test_norm_family(self):
        self.assertEqual(qe.norm_family('"Noto Sans TC", sans-serif'), "noto sans tc")
        self.assertEqual(qe.norm_family("Arial"), "arial")


# ------------------------------------------------------------------ #
class TestCompareProp(unittest.TestCase):
    def test_color_within_tolerance_matches(self):
        match, *_ = qe.compare_prop("color", "#212529", "rgb(33, 37, 41)")
        self.assertTrue(match)

    def test_color_out_of_tolerance_fails(self):
        match, *_ = qe.compare_prop("color", "#212529", "rgb(200, 0, 0)")
        self.assertFalse(match)

    def test_length_tolerance(self):
        self.assertTrue(qe.compare_prop("gap", "16px", "16.4px")[0])   # 差 0.4 < 1
        self.assertFalse(qe.compare_prop("gap", "16px", "20px")[0])

    def test_font_size_stricter_tolerance(self):
        self.assertTrue(qe.compare_prop("fontSize", "48px", "48.3px")[0])   # < 0.5
        self.assertFalse(qe.compare_prop("fontSize", "48px", "49px")[0])    # > 0.5

    def test_font_weight_exact(self):
        self.assertTrue(qe.compare_prop("fontWeight", 700, "700")[0])
        self.assertFalse(qe.compare_prop("fontWeight", 700, "400")[0])

    def test_unparseable_returns_none(self):
        match, *_ = qe.compare_prop("color", "#212529", "not-a-color")
        self.assertIsNone(match)


# ------------------------------------------------------------------ #
class TestAttribution(unittest.TestCase):
    def test_pass(self):
        self.assertEqual(qe.attribute(True, {"token": "x"}, True)[0], "PASS")

    def test_token_bound_mismatch_is_code(self):
        self.assertEqual(qe.attribute(False, {"token": "color/brand"}, True)[0], "CODE")

    def test_hardcode_mismatch_is_design(self):
        self.assertEqual(qe.attribute(False, {"token": None}, True)[0], "DESIGN")

    def test_missing_dom_needs_human(self):
        self.assertEqual(qe.attribute(None, {"token": "x"}, False)[0], "NEEDS_HUMAN")


# ------------------------------------------------------------------ #
class TestRunGuardrails(unittest.TestCase):
    def test_uncaptured_prop_not_counted_as_mismatch(self):
        """核心防護:DOM 未擷取的屬性不可判成程式/設計問題(必為 NEEDS_HUMAN)。"""
        figma = {"nodes": [{
            "frame": "F", "name": "n", "selector": "[data-figma-id='k']",
            "props": {"color": {"value": "#212529", "token": "color/ink"}},
        }]}
        dom = {"nodes": [{"selector": "[data-figma-id='k']", "computed": {}}]}
        rep = qe.run(figma, dom)
        row = rep["frames"][0]["rows"][0]
        self.assertEqual(row["responsibility"], "NEEDS_HUMAN")

    def test_missing_element_needs_human(self):
        figma = {"nodes": [{
            "frame": "F", "name": "n", "selector": "[data-figma-id='k']",
            "props": {"color": {"value": "#212529", "token": "color/ink"}},
        }]}
        dom = {"nodes": []}
        rep = qe.run(figma, dom)
        self.assertEqual(rep["frames"][0]["rows"][0]["responsibility"], "NEEDS_HUMAN")

    def test_score_all_pass_is_100(self):
        figma = {"nodes": [{
            "frame": "F", "name": "n", "selector": "[data-figma-id='k']",
            "props": {"color": {"value": "#212529", "token": "t"}},
        }]}
        dom = {"nodes": [{"selector": "[data-figma-id='k']",
                          "computed": {"color": "rgb(33,37,41)"}}]}
        rep = qe.run(figma, dom)
        self.assertEqual(rep["totals"]["score"], 100)


# ------------------------------------------------------------------ #
class TestAcceptedBaseline(unittest.TestCase):
    """Roadmap B:接受清單把可接受差異靜音,不阻擋分數但仍列出。"""

    def _spec_dom(self):
        figma = {"nodes": [{
            "frame": "F", "name": "主標", "selector": "[data-figma-id='hero:title']",
            "props": {"color": {"value": "#c70067", "token": "color/brand"}},
        }]}
        dom = {"nodes": [{"selector": "[data-figma-id='hero:title']",
                          "computed": {"color": "rgb(33, 37, 41)"}}]}  # 明顯不符 → CODE
        return figma, dom

    def test_without_baseline_is_code_and_low_score(self):
        figma, dom = self._spec_dom()
        rep = qe.run(figma, dom)
        self.assertEqual(rep["totals"]["CODE"], 1)
        self.assertEqual(rep["totals"]["score"], 0)

    def test_baseline_mutes_to_accepted(self):
        figma, dom = self._spec_dom()
        accepted = {"accepted": [{"key": "hero:title", "prop": "color",
                                  "reason": "已確認可接受"}]}
        rep = qe.run(figma, dom, accepted)
        t = rep["totals"]
        self.assertEqual(t["CODE"], 0)
        self.assertEqual(t["ACCEPTED"], 1)
        self.assertEqual(t["score"], 100)   # 已接受不阻擋分數
        row = rep["frames"][0]["rows"][0]
        self.assertEqual(row["responsibility"], "ACCEPTED")
        self.assertEqual(row["orig_responsibility"], "CODE")
        self.assertIn("已確認可接受", row["resp_msg"])

    def test_wildcard_prop_mutes_whole_node(self):
        figma, dom = self._spec_dom()
        accepted = {"accepted": [{"key": "hero:title", "prop": "*"}]}
        rep = qe.run(figma, dom, accepted)
        self.assertEqual(rep["totals"]["ACCEPTED"], 1)

    def test_selector_form_also_matches(self):
        figma, dom = self._spec_dom()
        accepted = [{"selector": "[data-figma-id='hero:title']", "prop": "color"}]
        rep = qe.run(figma, dom, accepted)
        self.assertEqual(rep["totals"]["ACCEPTED"], 1)

    def test_non_matching_entry_leaves_code(self):
        figma, dom = self._spec_dom()
        accepted = {"accepted": [{"key": "other", "prop": "color"}]}
        rep = qe.run(figma, dom, accepted)
        self.assertEqual(rep["totals"]["CODE"], 1)
        self.assertEqual(rep["totals"]["ACCEPTED"], 0)

    def test_pass_row_is_never_muted(self):
        figma = {"nodes": [{
            "frame": "F", "name": "n", "selector": "[data-figma-id='k']",
            "props": {"color": {"value": "#212529", "token": "t"}},
        }]}
        dom = {"nodes": [{"selector": "[data-figma-id='k']",
                          "computed": {"color": "rgb(33,37,41)"}}]}
        rep = qe.run(figma, dom, {"accepted": [{"key": "k", "prop": "*"}]})
        self.assertEqual(rep["frames"][0]["rows"][0]["responsibility"], "PASS")
        self.assertEqual(rep["totals"]["ACCEPTED"], 0)


# ------------------------------------------------------------------ #
class TestFrameNameAndCoverage(unittest.TestCase):
    def test_parse_frame_name(self):
        self.assertEqual(auto_qa.parse_frame_name("/about @1440"), ("/about", 1440))
        self.assertEqual(auto_qa.parse_frame_name("/pricing @375"), ("/pricing", 375))
        route, width = auto_qa.parse_frame_name("/no-width")
        self.assertEqual(route, "/no-width")
        self.assertIsNone(width)

    def test_coverage_matched_and_only(self):
        plan = [{"frame": "F", "url": "u", "width": 1440,
                 "keys": ["a", "b", "c"]}]
        cov = auto_qa.coverage(plan, {"b", "c", "d"})
        row = cov[0]
        self.assertEqual(row["matched"], ["b", "c"])
        self.assertEqual(row["design_only"], ["a"])   # 設計有、實作漏做
        self.assertEqual(row["dom_only"], ["d"])       # 實作有、設計未定義


# ------------------------------------------------------------------ #
class TestFigmaExtract(unittest.TestCase):
    def test_var_binding_detected_as_token(self):
        val, token = fx.unwrap("var(--color\\/brand,#c70067)")
        self.assertEqual(val, "#c70067")
        self.assertEqual(token, "color/brand")

    def test_hardcode_has_no_token(self):
        val, token = fx.unwrap("#c70067")
        self.assertEqual(val, "#c70067")
        self.assertIsNone(token)

    def test_parse_extracts_keyed_node_with_token(self):
        code = '''
        <div data-name="hero:title" className="text-[var(--fs\\/h1,48px)] font-bold">Hi</div>
        '''
        nodes = fx.parse(code, keys_only=True)
        self.assertEqual(len(nodes), 1)
        n = nodes[0]
        self.assertEqual(n["key"], "hero:title")
        self.assertEqual(n["props"]["fontSize"]["value"], 48)
        self.assertEqual(n["props"]["fontSize"]["token"], "fs/h1")
        self.assertEqual(n["props"]["fontWeight"]["value"], 700)


# ------------------------------------------------------------------ #
class TestRunDiff(unittest.TestCase):
    def test_resolved_and_regressed_detected(self):
        figma = load("demo_figma_nodes.json")
        prev = load("demo_dom_facts.json")
        curr = load("demo_dom_facts_v2.json")
        _, _, cats = run_diff.run(figma, prev, curr)
        resolved = {k[1] for (k, _, _) in cats["RESOLVED"]}
        regressed = {k[1] for (k, _, _) in cats["REGRESSED"]}
        self.assertIn("[data-figma-id='hero:title']", resolved)
        self.assertIn("[data-figma-id='seo:card']", regressed)


# ------------------------------------------------------------------ #
class TestIntegrationSamples(unittest.TestCase):
    def test_demo_auto_qa_runs(self):
        figma = load("demo_figma_nodes.json")
        dom = load("demo_dom_facts.json")
        rep, cov, plan = auto_qa.run(figma, dom)
        self.assertIn("score", rep["totals"])
        self.assertIn("iso:quote", cov[0]["design_only"])
        self.assertIn("promo:banner", cov[0]["dom_only"])

    def test_demo_accepted_file_mutes_hero_title(self):
        figma = load("demo_figma_nodes.json")
        dom = load("demo_dom_facts.json")
        accepted = load("demo_accepted.json")
        base, _, _ = auto_qa.run(figma, dom)
        acc, _, _ = auto_qa.run(figma, dom, accepted)
        self.assertGreaterEqual(acc["totals"]["ACCEPTED"], 1)
        self.assertLessEqual(acc["totals"]["CODE"], base["totals"]["CODE"] - 1)
        self.assertGreaterEqual(acc["totals"]["score"], base["totals"]["score"])

    def test_mx_real_case_locked_at_80(self):
        """CLAUDE.md 規定:MX 真實案例應穩定得到 80%。"""
        figma = load("mx_figma_spec.json")
        dom = load("mx_dom_facts.json")
        rep = qe.run(figma, dom)
        self.assertEqual(rep["totals"]["score"], 80)


if __name__ == "__main__":
    unittest.main(verbosity=2)
