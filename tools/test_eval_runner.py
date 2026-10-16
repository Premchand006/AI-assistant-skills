#!/usr/bin/env python3
"""Unit tests for the eval harness's failure semantics.

The harness's job is to keep the published results honest, so these cover the
ways it could lie: grading a runner error as a model answer, counting a missing
transcript as anything but missing, exiting 0 when evidence is incomplete,
writing a transcript outside the transcript root, and recording a response that
contains a secret. Standard library only.

    python tools/test_eval_runner.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))
sys.path.insert(0, str(REPO / "tools"))

import eval_runner as er  # noqa: E402
from check_transcripts import scan_text  # noqa: E402


class FakeRunner:
    name = "fake"

    def __init__(self, gen):
        self.gen = gen

    def generate(self, prompt, system="", key=""):
        return self.gen


def suite(**kw):
    base = dict(skill="demo", path=Path("."), skill_md="", description="d",
                cases=[er.Case(id="c1", prompt="p", graders={"must_match": "yes"})],
                should_trigger=["x"], should_not_trigger=["y"])
    base.update(kw)
    return er.Suite(**base)


class TranscriptPaths(unittest.TestCase):
    def test_accepts_normal_keys(self):
        root = Path(tempfile.mkdtemp())
        p = er.transcript_path(root, "rtl-verilog-lint/fix-latch.on")
        self.assertEqual(p, (root / "rtl-verilog-lint" / "fix-latch.on.md").resolve())

    def test_rejects_traversal_and_odd_names(self):
        root = Path(tempfile.mkdtemp())
        for key in ("../escape.on", "demo/../../x.on", "/abs/x.on", "demo/.hidden",
                    "demo/-flag", "Demo/UPPER.on", "demo/a b.on", "demo/a\\b.on", ""):
            with self.subTest(key=key), self.assertRaises(ValueError):
                er.transcript_path(root, key)


class Statuses(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(er.classify_text("").status, er.EMPTY)
        self.assertEqual(er.classify_text("  \n").status, er.EMPTY)
        self.assertEqual(er.classify_text("[runner error] boom").status, er.RUNNER_ERROR)
        self.assertEqual(er.classify_text("an answer").status, er.OK)

    def test_replay_missing_and_legacy_error(self):
        root = Path(tempfile.mkdtemp())
        (root / "demo").mkdir()
        (root / "demo" / "c1.on.md").write_text("[runner error] 529 overloaded")
        r = er.ReplayRunner(root)
        self.assertEqual(r.generate("p", key="demo/c1.on").status, er.RUNNER_ERROR)
        self.assertEqual(r.generate("p", key="demo/c1.off").status, er.MISSING)
        self.assertEqual(r.missing, ["demo/c1.off"])

    def test_runner_error_is_not_graded(self):
        # The error text matches the grader; it must still not pass.
        gen = er.Generation(er.RUNNER_ERROR, error="yes, it failed")
        rows = er.run_usefulness(suite(), FakeRunner(gen), ["on"])
        mode = rows[0]["modes"]["on"]
        self.assertFalse(mode["passed"])
        self.assertFalse(mode["available"])
        self.assertEqual(mode["checks"], [])
        self.assertEqual(mode["status"], er.RUNNER_ERROR)

    def test_ok_is_graded(self):
        rows = er.run_usefulness(suite(), FakeRunner(er.Generation(er.OK, "yes")), ["on"])
        self.assertTrue(rows[0]["modes"]["on"]["passed"])

    def test_discovery_error_never_passes_negative(self):
        # A failed call picks nothing, which used to count as "correctly stayed quiet".
        gen = er.Generation(er.TIMEOUT, error="slow")
        res = er.run_discovery([suite()], FakeRunner(gen), suite())
        self.assertFalse(res["should_not_trigger"][0]["passed"])
        self.assertFalse(res["should_not_trigger"][0]["available"])

    def test_summary_counts_errors_and_ratios(self):
        s = suite()
        report = {"skills": {"demo": {
            "usefulness": er.run_usefulness(s, FakeRunner(er.Generation(er.TIMEOUT)), ["on", "off"]),
            "discovery": {
                "should_trigger": [{"available": True, "passed": True, "status": er.OK},
                                   {"available": False, "passed": False, "status": er.MISSING}],
                "should_not_trigger": [],
            },
        }}}
        row = er.summarise(report)[0]
        self.assertEqual(row["errors"], 2)
        self.assertEqual(row["missing"], 1)
        self.assertEqual(row["graded"], 0)
        self.assertEqual(row["discovery_hit"], "1/1 (of 2)")
        self.assertEqual(row["adversarial_clean"], "-")


class SuiteLoading(unittest.TestCase):
    def _skills(self, yaml_text):
        root = Path(tempfile.mkdtemp())
        d = root / "demo" / "evals"
        d.mkdir(parents=True)
        (root / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: d\n---\nbody\n")
        (d / "eval.yaml").write_text(yaml_text)
        return root

    def test_rejects_unsafe_case_id(self):
        root = self._skills("usefulness:\n  - id: ../../etc\n    prompt: p\n")
        with self.assertRaises(ValueError):
            er.load_suites(root, [])

    def test_rejects_duplicate_case_id(self):
        root = self._skills(
            "usefulness:\n  - id: a\n    prompt: p\n  - id: a\n    prompt: q\n")
        with self.assertRaises(ValueError):
            er.load_suites(root, [])

    def test_repo_suites_load(self):
        suites = er.load_suites(REPO / "skills", [])
        self.assertTrue(suites)
        self.assertTrue(all(s.suite_hash for s in suites))


class ExitCodes(unittest.TestCase):
    def _main(self, *argv):
        out = Path(tempfile.mkdtemp())
        old = sys.argv
        sys.argv = ["eval_runner.py", "--runner", "replay", "--skill", "rtl-verilog-lint",
                    "--transcripts", str(out / "t"), "--out", str(out / "r.json"), *argv]
        try:
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                return er.main()
        finally:
            sys.argv = old

    def test_missing_is_preview_by_default(self):
        self.assertEqual(self._main(), 0)

    def test_fail_on_missing(self):
        self.assertEqual(self._main("--fail-on-missing"), 1)


class TranscriptScan(unittest.TestCase):
    def test_catches_secrets(self):
        text = ("key sk-ant-api03-abcdefghijklmnopqrstuvwxyz\n"
                "-----BEGIN RSA PRIVATE KEY-----\n"
                "mail jane.doe@acme-corp.com\n"
                "path /home/jdoe/project\n")
        rules = {h[0] for h in scan_text(text)}
        self.assertTrue({"anthropic-key", "private-key", "email", "home-path"} <= rules)

    def test_secret_not_echoed(self):
        hits = scan_text("sk-ant-api03-abcdefghijklmnopqrstuvwxyz")
        self.assertNotIn("abcdefghijklmnop", hits[0][2])

    def test_allows_documentation_values(self):
        text = ("contact dev@example.com\n"
                "run from /home/<user>/work\n"
                "real@person.io  # transcript-scan: allow\n"
                "always @(posedge clk) begin\n")
        self.assertEqual(scan_text(text), [])

    def test_committed_transcripts_are_clean(self):
        for f in (REPO / "evals" / "transcripts").rglob("*.md"):
            with self.subTest(f=f.name):
                self.assertEqual(scan_text(f.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
