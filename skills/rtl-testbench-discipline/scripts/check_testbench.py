#!/usr/bin/env python3
"""Check a testbench for the properties that make it worth running.

A testbench that prints waveforms for a human to read is a demo. A testbench
that decides pass or fail by itself, cannot hang, and says why it failed is a
regression test. This looks for the difference.

Handles SystemVerilog/Verilog testbenches (.v, .sv) and cocotb testbenches
(.py). The checks are structural: they find testbenches that cannot fail, not
testbenches that check the wrong thing.

Usage:
    python check_testbench.py tb/ [--json] [--fail-on error|warn]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ("error", "warn", "info")


class Finding:
    def __init__(self, sev, rule, file, line, message, hint=""):
        self.sev, self.rule, self.file = sev, rule, file
        self.line, self.message, self.hint = line, message, hint

    def as_dict(self):
        return {"severity": self.sev, "rule": self.rule, "file": self.file,
                "line": self.line, "message": self.message, "hint": self.hint}

    def render(self):
        s = "%s:%d: %s: [%s] %s" % (self.file, self.line, self.sev, self.rule, self.message)
        if self.hint:
            s += "\n    hint: " + self.hint
        return s


def strip_comments_hdl(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def strip_comments_py(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


# --------------------------------------------------------------------------
# SystemVerilog testbenches
# --------------------------------------------------------------------------


CHECK_PATTERNS = [
    r"\bassert\s*\(",                  # immediate or concurrent assertion
    r"\$error\b", r"\$fatal\b",
    r"!==|!=",                         # a comparison against an expected value
    r"\bcompare\w*\s*\(", r"\bcheck\w*\s*\(",
    r"\bscoreboard\b",
]


def check_sv(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = strip_comments_hdl(raw)
    name = path.name
    out = []

    def add(sev, rule, pos, msg, hint=""):
        out.append(Finding(sev, rule, name, line_of(src, pos), msg, hint))

    has_checks = any(re.search(p, src) for p in CHECK_PATTERNS)
    displays = len(re.findall(r"\$(display|write|monitor)\b", src))

    if not has_checks:
        add("error", "no-self-check", 0,
            "no assertion or comparison against an expected value",
            "a testbench with %d print statement(s) and no check cannot fail, so it "
            "cannot catch a regression; compare against an expected value and count "
            "mismatches" % displays)
    elif displays > 20 and len(re.findall(r"\bassert\s*\(|\$error\b|\$fatal\b", src)) < 2:
        add("warn", "print-heavy", 0,
            "%d print statements against almost no assertions" % displays,
            "printing is for diagnosing a failure the testbench already detected")

    # watchdog
    has_watchdog = re.search(
        r"initial\s+begin[^e]{0,200}?#\s*[\w']+\s*;?\s*\$(fatal|finish|error)", src, re.S
    ) or re.search(r"\$timeformat|watchdog|timeout", src, re.I)
    if not has_watchdog:
        add("error", "no-timeout", 0,
            "no watchdog timeout",
            "a testbench that waits on a signal the DUT never asserts hangs forever and "
            "takes a CI runner with it; add an initial block that calls $fatal after a "
            "bounded time")

    # final status
    if not re.search(r"\$(fatal|error)\b", src) and not re.search(
        r"(errors?|fail\w*|mismatch\w*)\s*(==|!=|>|\+\+|\+=)", src, re.I
    ):
        add("warn", "no-final-status", 0,
            "no error counter and no $fatal",
            "a simulation that exits with status 0 after failing looks like a pass to "
            "CI; count errors and end with $fatal when the count is non-zero")

    # driving on the active edge
    for m in re.finditer(r"@\s*\(\s*posedge\s+(\w*clk\w*)\s*\)\s*([A-Za-z_]\w*)\s*=(?!=)", src):
        add("warn", "drive-on-active-edge", m.start(),
            "stimulus driven with a blocking assignment on the same edge the DUT samples",
            "drive on the opposite edge, or use <=, so the DUT sees a stable value "
            "instead of racing the testbench")

    if not re.search(r"\brst|\breset", src, re.I):
        add("warn", "no-reset", 0, "reset is never exercised",
            "reset behaviour is where a surprising share of RTL bugs live")

    if re.search(r"\$finish\b", src) and not re.search(r"\$(fatal|error)\b", src):
        add("info", "finish-without-status", 0,
            "$finish is used but $fatal never is",
            "$finish exits 0; a failing test that exits 0 is a green CI run")

    if not re.search(r"\$(urandom|random)|randomize\s*\(|std::randomize", src):
        add("info", "no-randomisation", 0,
            "only directed stimulus",
            "directed tests find the bugs you thought of; add constrained random for "
            "the rest, with a seed printed so a failure can be reproduced")

    if not re.search(r"\bcovergroup\b|\bcover\s+property|\bcoverpoint\b", src):
        add("info", "no-coverage", 0,
            "no functional coverage",
            "without coverage there is no evidence about what the tests did not reach")

    if re.search(r"\$dumpvars", src) and not re.search(r"ifdef|ifndef", src):
        add("info", "unconditional-dump", 0,
            "waveform dumping is unconditional",
            "dumping every signal of every run is slow in CI; put it behind `ifdef WAVES")

    return out


# --------------------------------------------------------------------------
# cocotb testbenches
# --------------------------------------------------------------------------


def check_cocotb(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = strip_comments_py(raw)
    name = path.name
    out = []

    if not re.search(r"@cocotb\.test|@test\b", src):
        return out  # not a cocotb testbench

    def add(sev, rule, pos, msg, hint=""):
        out.append(Finding(sev, rule, name, line_of(src, pos), msg, hint))

    tests = re.findall(r"@cocotb\.test[^\n]*\n\s*async def (\w+)", src)
    if not re.search(r"\bassert\b|raise TestFailure|\.value\s*==", src):
        add("error", "no-self-check", 0,
            "no assert in any of the %d test(s)" % len(tests),
            "cocotb reports a test as passing unless an assertion raises, so a test "
            "without one always passes")

    if not re.search(r"with_timeout|timeout_time\s*=", src):
        add("error", "no-timeout", 0,
            "no timeout on any test",
            "pass timeout_time and timeout_unit to @cocotb.test(), or wrap awaits in "
            "cocotb.triggers.with_timeout, so a hung DUT fails instead of blocking CI")

    if re.search(r"await\s+RisingEdge\(\s*dut\.\w*clk\w*\s*\)\s*\n\s*dut\.\w+\.value\s*=", src):
        add("warn", "drive-on-active-edge", 0,
            "stimulus assigned immediately after RisingEdge on the clock",
            "assign after FallingEdge, or add a small Timer, so the DUT samples a "
            "settled value")

    if not re.search(r"\brandom\b|\.randomize\(|randint|choice\(", src):
        add("info", "no-randomisation", 0, "only directed stimulus",
            "seed a random generator and log the seed so failures reproduce")

    if not re.search(r"\bcaplog\b|_log\.|logging", src):
        add("info", "no-logging", 0, "no use of the cocotb logger",
            "dut._log.info carries the test name and simulation time, which print does not")

    return out


# --------------------------------------------------------------------------


def looks_like_testbench(path: Path) -> bool:
    if path.suffix == ".py":
        return True
    if re.search(r"(^|_)(tb|test|testbench)(_|$)", path.stem, re.IGNORECASE):
        return True
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return False
    return bool(re.search(r"\binitial\b", head) and re.search(r"\$(display|finish|dumpvars)", head))


def collect(targets) -> list:
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(
                f for f in sorted(p.rglob("*"))
                if f.suffix in (".v", ".sv", ".py") and looks_like_testbench(f)
            )
        elif p.is_file():
            files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--fail-on", choices=("error", "warn", "info", "never"), default="error")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = collect(args.targets)
    if not files:
        print("no testbench files matched", file=sys.stderr)
        return 2

    findings = []
    for f in files:
        findings.extend(check_cocotb(f) if f.suffix == ".py" else check_sv(f))
    findings.sort(key=lambda f: (SEVERITIES.index(f.sev), f.file, f.line))

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(f.render())
        counts = {s: sum(1 for f in findings if f.sev == s) for s in SEVERITIES}
        print("\n%d testbench file(s) checked: %d error, %d warn, %d info"
              % (len(files), counts["error"], counts["warn"], counts["info"]))
        print("These are structural checks. A testbench can pass all of them and still "
              "check the wrong behaviour.")

    if args.fail_on == "never":
        return 0
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.sev) <= threshold for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
