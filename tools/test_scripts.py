#!/usr/bin/env python3
"""Run every bundled skill script against the fixtures and check the findings.

The fixtures under evals/fixtures/ contain planted defects. Each case below
names the rules the script is expected to fire on, and the rules it must not
fire on for the clean fixtures. This is what keeps a refactor of a checker from
quietly turning it into a script that reports nothing.

Usage:
    python tools/test_scripts.py            # run all
    python tools/test_scripts.py -v         # show each script's output
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable

# (label, argv, expected rules present, rules that must be absent)
CASES = [
    (
        "rtl-verilog-lint / broken RTL",
        ["skills/rtl-verilog-lint/scripts/check_synthesizable.py",
         "evals/fixtures/rtl/bad_fifo.sv", "--json", "--fail-on", "never"],
        {"unsynthesisable-type", "initial-block", "mixed-sensitivity",
         "blocking-in-sequential", "latch-from-case", "delay-control",
         "multiple-drivers", "system-task", "default-nettype"},
        set(),
    ),
    (
        "rtl-verilog-lint / clean RTL",
        ["skills/rtl-verilog-lint/scripts/check_synthesizable.py",
         "evals/fixtures/rtl/good_counter.sv", "--json", "--fail-on", "never"],
        set(),
        {"blocking-in-sequential", "latch-from-case", "initial-block",
         "multiple-drivers", "default-nettype", "mixed-sensitivity"},
    ),
    (
        "timing-closure-cdc / mixed crossings",
        ["skills/timing-closure-cdc/scripts/cdc_scan.py",
         "evals/fixtures/rtl/cdc_mixed.sv", "--json", "--fail-on", "never"],
        {"multibit-2ff", "single-flop-sync", "shared-async-reset",
         "synchronised-crossing"},
        {"unsynchronised-crossing"},   # req_fast is correctly synchronised
    ),
    (
        "timing-closure-cdc / single domain",
        ["skills/timing-closure-cdc/scripts/cdc_scan.py",
         "evals/fixtures/rtl/good_counter.sv", "--json", "--fail-on", "never"],
        set(),
        {"multibit-2ff", "single-flop-sync", "unsynchronised-crossing"},
    ),
    (
        "rtl-testbench-discipline / weak testbench",
        ["skills/rtl-testbench-discipline/scripts/check_testbench.py",
         "evals/fixtures/tb/weak_tb.sv", "--json", "--fail-on", "never"],
        {"no-self-check", "no-timeout", "drive-on-active-edge", "no-reset"},
        set(),
    ),
    (
        "embedded-firmware-misra / unsafe ISR",
        ["skills/embedded-firmware-misra/scripts/check_isr_safety.py",
         "evals/fixtures/firmware/uart_driver.c", "--json", "--fail-on", "never"],
        {"missing-volatile", "blocking-call-in-isr", "unprotected-rmw",
         "busy-wait-no-timeout", "dynamic-memory", "unparenthesised-macro"},
        set(),
    ),
    (
        "openlane-sky130-flow / broken config",
        ["skills/openlane-sky130-flow/scripts/check_config.py",
         "evals/fixtures/openlane/config.json", "--json"],
        {"PDK", "CLOCK_PORT", "FP_CORE_UTIL", "FP_SIZING", "meta",
         "VERILOG_FILES", "CLOCK_PERIOD"},
        set(),
        "key",
    ),
    (
        "openlane-sky130-flow / failed run",
        ["skills/openlane-sky130-flow/scripts/summarize_run.py",
         "evals/fixtures/openlane/runs", "--json"],
        set(),
        set(),
        "run-summary",
    ),
]


def run(argv, verbose=False):
    proc = subprocess.run(
        [PY] + argv, cwd=REPO, capture_output=True, text=True, timeout=180
    )
    if verbose:
        print(proc.stdout)
        if proc.stderr.strip():
            print(proc.stderr, file=sys.stderr)
    return proc


def rules_from(stdout: str, field: str) -> set:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return set()
    if isinstance(data, list):
        return {d.get(field, "") for d in data if isinstance(d, dict)}
    return set()


def check_run_summary(stdout: str) -> list:
    """The summariser has its own shape, so it gets its own assertions."""
    errors = []
    try:
        s = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return ["output is not JSON: %s" % exc]
    if s.get("completed"):
        errors.append("reported the failed fixture run as completed")
    if s.get("last_step") != "openroad-globalrouting":
        errors.append("last_step is %r, expected openroad-globalrouting" % s.get("last_step"))
    found = {v["metric"] for v in s.get("violations", [])}
    for expected in ("timing__setup__ws", "route__drc_errors"):
        if expected not in found:
            errors.append("did not flag %s as a violation" % expected)
    if s.get("metrics", {}).get("design__instance__count") != 4820:
        errors.append("did not merge metrics from the earlier step directory")
    if not s.get("errors"):
        errors.append("did not surface error.log")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    failed = 0
    for case in CASES:
        label, argv, expected, forbidden = case[0], case[1], case[2], case[3]
        mode = case[4] if len(case) > 4 else "rule"

        proc = run(argv, args.verbose)
        problems = []
        if proc.returncode not in (0, 1):
            problems.append("exited %d\n%s" % (proc.returncode, proc.stderr.strip()[:400]))
        elif mode == "run-summary":
            problems.extend(check_run_summary(proc.stdout))
        else:
            found = rules_from(proc.stdout, "rule" if mode == "rule" else "key")
            missing = expected - found
            leaked = forbidden & found
            if missing:
                problems.append("did not report: %s" % ", ".join(sorted(missing)))
            if leaked:
                problems.append("falsely reported: %s" % ", ".join(sorted(leaked)))
            if not expected and not forbidden and not found:
                problems.append("produced no findings at all")

        if problems:
            failed += 1
            print("FAIL  %s" % label)
            for p in problems:
                print("      %s" % p)
        else:
            print("PASS  %s" % label)

    print("\n%d/%d script checks passed" % (len(CASES) - failed, len(CASES)))
    if failed:
        return 1

    print(
        "\nNot covered here: skills/onnx-quantize-tflm/scripts/tflite_report.py, "
        "which needs a real .tflite model and a TFLite interpreter. Its import "
        "handling is checked by tools/smoke_imports.py; its report path is not."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
