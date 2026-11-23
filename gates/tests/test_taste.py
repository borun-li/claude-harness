#!/usr/bin/env python3
"""Taste measures: what a captured page measures against the configured values is reported by
`capture` and `fe-verify`, and fails nothing.
Run: python3 -m pytest tests/test_taste.py -q"""
import json
import pathlib
import socket
import subprocess
import sys
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from test_frontend_gates import PY, RUN, TERMINAL_PLAN, VERIFY, FrontBase  # noqa: E402
from test_frontend_v15 import ctx_of  # noqa: E402
from test_gates import GATE  # noqa: E402

sys.path.insert(0, str(GATE.parent))
from gatelib import taste  # noqa: E402

CFG = {"font_families_max": 2, "radius_px": [0, 4, 6], "body_px": 14, "gradients_max": 0, "dialogs_open_max": 1}
CLEAN = {"fonts": {"Inter": {"count": 900, "example": "p"}, "Georgia": {"count": 40, "example": "h1"}},
         "code_fonts": {"Menlo": {"count": 30, "example": "code"}},
         "text_px": {"14px": {"count": 800, "example": "p"}, "20px": {"count": 140, "example": "h1"}},
         "radii": {"4px": {"count": 6, "example": "button"}, "6px": {"count": 2, "example": "div.card"},
                   "round": {"count": 1, "example": "img.avatar"}},
         "gradients": [], "dialogs_open": ["div.drawer"]}
OFF = {"fonts": {"Inter": {"count": 900, "example": "p"}, "Georgia": {"count": 40, "example": "h1"},
                 "Arial": {"count": 12, "example": "button#go"}},
       "code_fonts": {},
       "text_px": {"16px": {"count": 700, "example": "p.lead"}, "14px": {"count": 300, "example": "td"}},
       "radii": {"12px": {"count": 3, "example": "div.card"}, "4px": {"count": 6, "example": "button"}},
       "gradients": ["div.hero"], "dialogs_open": ["div.modal", "div.confirm"]}


class PageNotes(unittest.TestCase):
    def test_a_page_within_the_values_has_no_note(self):
        self.assertEqual(taste.page_notes(CLEAN, CFG), [])

    def test_each_measure_names_what_it_found_and_where(self):
        notes = taste.page_notes(OFF, CFG)
        self.assertEqual(len(notes), 5)
        joined = "\n".join(notes)
        self.assertIn("3 font families outside code (Inter, Georgia, Arial); at most 2", joined)
        self.assertIn("`Arial` is on `button#go`", joined)
        self.assertIn("corner radius 12px on `div.card`; the values are 4 px, 6 px or fully round", joined)
        self.assertIn("most text is 16px (70% of the characters, e.g. `p.lead`); body text is 14 px", joined)
        self.assertIn("1 gradient backgrounds (`div.hero`); at most 0", joined)
        self.assertIn("2 dialogs open at once (`div.modal`, `div.confirm`); at most 1", joined)

    def test_code_fonts_and_round_corners_are_not_counted(self):
        page = {**CLEAN, "code_fonts": {"Menlo": {"count": 1, "example": "code"}, "Courier": {"count": 1, "example": "pre"}}}
        self.assertEqual(taste.page_notes(page, CFG), [])

    def test_a_null_value_leaves_its_measure_out(self):
        notes = taste.page_notes(OFF, {**CFG, "radius_px": None, "gradients_max": None})
        self.assertEqual(len(notes), 3)
        self.assertFalse(any("radius" in n or "gradient" in n for n in notes))


class Reported(FrontBase):
    """In a run: measured for a tool-class product, reported by `fe-verify`, never a failure."""
    def setUp(self):
        super().setUp()
        self.to_build()

    def round_with(self, pages):
        self.p.write("web/notice.html", '<p class="warn">Already uploaded</p>')
        self.p.write(f"{RUN}/capture-plan.json", json.dumps(TERMINAL_PLAN))
        code, out = self.capture()
        assert code == 0, out
        d = self.p.fe / "evidence" / "verify-1"
        manifest = json.loads((d / "manifest.json").read_text())
        entry = manifest["entries"][0]
        manifest["entries"] = []
        for size, facts in pages.items():
            name = f"{entry['id']}@{size}.page.json"
            (d / name).write_text(json.dumps(facts))
            manifest["entries"].append({**entry, "size": size, "files": {**entry["files"], "page.json": name}})
        (d / "manifest.json").write_text(json.dumps(manifest))
        return d

    def test_one_difference_at_two_sizes_is_one_line(self):
        d = self.round_with({"desktop": OFF, "phone": OFF})
        self.set_state(product_class="tool")
        lines, pages, why = taste.notes(ctx_of(self.p.root), d)
        self.assertEqual((pages, why, len(lines)), (2, None, 5))
        self.assertTrue(all(line.endswith("— Q-001-dup@desktop, Q-001-dup@phone") for line in lines), lines)

    def test_not_measured_unless_the_product_is_a_tool(self):
        d = self.round_with({"desktop": OFF})
        self.assertIn("product_class is None", taste.notes(ctx_of(self.p.root), d)[2])
        self.set_state(product_class="showcase")
        self.assertIn("product_class is 'showcase'", taste.notes(ctx_of(self.p.root), d)[2])
        self.p.write(".claude/harness.json", json.dumps({"product_class": "tool"}))
        self.set_state(product_class=None)
        self.assertEqual(len(taste.notes(ctx_of(self.p.root), d)[0]), 5)

    def test_a_project_sets_its_own_values(self):
        d = self.round_with({"desktop": OFF})
        self.set_state(product_class="tool")
        self.p.write(".claude/harness.json", json.dumps({"taste": {"radius_px": [0, 4, 12], "body_px": 16,
                                                                   "font_families_max": 3}}))
        lines = taste.notes(ctx_of(self.p.root), d)[0]
        self.assertEqual(len(lines), 2, lines)  # the gradient and the two dialogs are left

    def test_fe_verify_reports_and_does_not_fail_on_it(self):
        self.round_with({"desktop": OFF})
        self.set_state(product_class="tool")
        self.fe_dispatch("fe-tester")
        self.p.write(f"{RUN}/04-verification.md", VERIFY + "\n".join(["filler"] * 8))
        _, out, rep = self.fe("fe-verify")
        hit = next(c for c in rep["checks"] if c["id"] == "FE4.taste")
        self.assertEqual(hit["status"], "pass")
        self.assertEqual(len(hit["details"]), 5)
        self.assertNotIn("FE4.taste", json.dumps(rep["fail_by_owner"]))
        self.assertEqual(len(rep["data"]["reported"]), 5)
        self.assertIn("[gate] reported, fails nothing: FE4.taste: 3 font families", out)

    def test_fe_verify_says_nothing_for_another_class(self):
        self.round_with({"desktop": OFF})
        self.fe_dispatch("fe-tester")
        self.p.write(f"{RUN}/04-verification.md", VERIFY + "\n".join(["filler"] * 8))
        _, out, rep = self.fe("fe-verify")
        self.assertFalse([c for c in rep["checks"] if c["id"] == "FE4.taste"])
        self.assertNotIn("reported, fails nothing", out)

    def test_state_refuses_an_unknown_class(self):
        self.set_state(product_class="dashboard")
        hit = next(c for c in self.fe("fe-ux")[2]["checks"] if c["id"] == "ALL.state")
        self.assertEqual(hit["status"], "fail")
        self.assertIn("product_class must be tool|showcase, got 'dashboard'", hit["details"])

    def test_real_chrome_measures_the_rendered_page(self):
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not (GATE.parent / "node_modules" / "playwright-core").exists() or not pathlib.Path(chrome).exists():
            self.skipTest("playwright-core or Chrome not installed")
        site = self.p.root / "site"
        site.mkdir()
        (site / "index.html").write_text("""<html><body style="font-family: Helvetica; font-size: 16px">
<h1 style="font-family: Georgia">Orders</h1>
<p>Forty characters of body text, set at sixteen pixels here.</p>
<p>Read <code style="font-family: Courier">gate.py</code> first.</p>
<button style="font-family: Times; padding: 16px 24px; border: 1px solid #000; border-radius: 12px">Export</button>
<img alt="" style="width: 40px; height: 40px; border-radius: 50%; background-color: #ccc">
<span style="display: inline-block; padding: 2px 8px; border: 1px solid #000; border-radius: 4px">Paid</span>
<div class="hero" style="height: 40px; background-image: linear-gradient(#fff, #ddf)"></div>
<p hidden style="font-family: Impact">never shown</p>
<div role="dialog" class="outer" style="border: 1px solid #000">Delete?
  <div role="alertdialog" class="inner" style="border: 1px solid #000">Sure?</div></div>
</body></html>""")
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen([PY, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=site,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(0.8)
            self.set_state(product_class="tool")
            self.p.write(f"{RUN}/capture-plan.json", json.dumps({
                "surface": "web", "base_url": f"http://127.0.0.1:{port}",
                "sizes": [{"name": "desktop", "width": 1280, "height": 800}],
                "captures": [{"id": "Q-001-dup", "row": "Q-001", "state": "duplicate", "url": "/index.html"}]}))
            code, out = self.capture()
            self.assertEqual(code, 0, out)
            facts = json.loads((self.p.fe / "evidence" / "verify-1" / "Q-001-dup@desktop.page.json").read_text())
            self.assertEqual(set(facts["fonts"]), {"Helvetica", "Georgia", "Times"})  # not Courier, not the hidden Impact
            self.assertEqual(set(facts["code_fonts"]), {"Courier"})
            self.assertEqual(set(facts["radii"]), {"12px", "4px", "round"})
            self.assertEqual(facts["radii"]["12px"]["example"], "button")
            self.assertEqual(facts["gradients"], ["div.hero"])
            self.assertEqual(facts["dialogs_open"], ["div.outer", "div.inner"])
            self.assertEqual(max(facts["text_px"], key=lambda k: facts["text_px"][k]["count"]), "16px")
            for want in ("3 font families outside code", "corner radius 12px on `button`", "most text is 16px",
                         "1 gradient backgrounds (`div.hero`)", "2 dialogs open at once"):
                self.assertIn(f"reported, fails nothing: FE4.taste: {want}", out)
        finally:
            srv.terminate()


if __name__ == "__main__":
    unittest.main()
