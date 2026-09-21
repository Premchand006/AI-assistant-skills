#!/usr/bin/env python3
"""Summarise an OpenLane 2 run directory: where it stopped and what it produced.

A run directory is hundreds of files across dozens of step folders. This pulls
out the four things worth knowing first: did it finish, which step stopped it,
what the sign-off numbers are, and which of those numbers are out of bounds.

Usage:
    python summarize_run.py runs/RUN_2026-09-21_10-00-00
    python summarize_run.py runs/            # picks the newest run
    python summarize_run.py runs/latest --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# OpenLane 2 metric names, with the direction that counts as bad.
# (metric, label, comparison, threshold)  comparison: "lt" flags value < t.
SIGNOFF = [
    ("timing__setup__ws", "setup worst slack (ns)", "lt", 0.0),
    ("timing__hold__ws", "hold worst slack (ns)", "lt", 0.0),
    ("timing__setup__tns", "setup total neg slack (ns)", "lt", 0.0),
    ("route__drc_errors", "routing DRC errors", "gt", 0),
    ("magic__drc_error__count", "Magic DRC errors", "gt", 0),
    ("design__lvs_error__count", "LVS errors", "gt", 0),
    ("antenna__violating__nets", "antenna violating nets", "gt", 0),
    ("synthesis__check_error__count", "synthesis check errors", "gt", 0),
    ("design__max_slew_violation__count", "max slew violations", "gt", 0),
    ("design__max_cap_violation__count", "max cap violations", "gt", 0),
]
CONTEXT = [
    ("design__instance__count", "cell count"),
    ("design__instance__utilization", "core utilisation"),
    ("design__die__area", "die area (um^2)"),
    ("design__core__area", "core area (um^2)"),
    ("power__total", "total power (W)"),
    ("clock__skew__worst", "worst clock skew (ns)"),
]

STEP_DIR_RE = re.compile(r"^(\d+)-(.+)$")


def newest_run(path: Path) -> Path:
    """If given a runs/ parent, pick the most recently modified run inside it."""
    if (path / "resolved.json").exists() or any(
        STEP_DIR_RE.match(p.name) for p in path.iterdir() if p.is_dir()
    ):
        return path
    candidates = [p for p in path.iterdir() if p.is_dir()]
    if not candidates:
        return path
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_metrics(run: Path) -> dict:
    """Merge metrics in step order so the last writer of each key wins."""
    metrics = {}
    sources = []
    step_files = sorted(
        (p for p in run.glob("*/*.json") if p.name in ("metrics.json", "state_out.json")),
        key=lambda p: p.parent.name,
    )
    for p in step_files + [run / "final" / "metrics.json"]:
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        found = data.get("metrics", data) if isinstance(data, dict) else {}
        if isinstance(found, dict):
            flat = {k: v for k, v in found.items() if isinstance(v, (int, float, str))}
            if flat:
                metrics.update(flat)
                sources.append(p)
    return metrics, sources


def list_steps(run: Path) -> list:
    steps = []
    for p in sorted(run.iterdir()):
        if not p.is_dir():
            continue
        m = STEP_DIR_RE.match(p.name)
        if m:
            steps.append((int(m.group(1)), m.group(2), p))
    return steps


def tail(path: Path, n: int = 40) -> list:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [ln for ln in lines if ln.strip()][-n:]


def as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def summarise(run: Path) -> dict:
    steps = list_steps(run)
    metrics, sources = load_metrics(run)
    final = run / "final"
    gds = sorted(final.rglob("*.gds")) if final.is_dir() else []

    violations = []
    for key, label, cmp_, threshold in SIGNOFF:
        if key not in metrics:
            continue
        v = as_float(metrics[key])
        if v is None:
            continue
        bad = v < threshold if cmp_ == "lt" else v > threshold
        if bad:
            violations.append({"metric": key, "label": label, "value": v})

    errors = tail(run / "error.log", 30)
    warnings = tail(run / "warning.log", 15)

    return {
        "run": str(run),
        "steps_run": len(steps),
        "last_step": steps[-1][1] if steps else None,
        "completed": bool(gds) or (final.is_dir() and any(final.iterdir())),
        "gds": [str(g) for g in gds],
        "metrics": metrics,
        "metric_sources": [str(s) for s in sources],
        "violations": violations,
        "errors": errors,
        "warnings": warnings,
    }


def render(s: dict) -> str:
    out = ["run: %s" % s["run"]]
    out.append("steps executed: %d, last: %s" % (s["steps_run"], s["last_step"] or "none"))
    if s["completed"]:
        out.append("status: reached final/")
        for g in s["gds"]:
            out.append("  GDS: %s" % g)
    else:
        out.append("status: did not reach final/ - the run stopped early")

    if s["errors"]:
        out.append("\nerror.log (last lines):")
        out.extend("  " + ln for ln in s["errors"])
        out.append(
            "\nThe step directory named above holds the tool log with the real cause; "
            "error.log only carries what the flow surfaced."
        )

    if s["violations"]:
        out.append("\nsign-off violations:")
        for v in s["violations"]:
            out.append("  %-32s %s" % (v["label"], v["value"]))
    elif s["metrics"]:
        out.append("\nsign-off: no violations in the metrics that were reported")

    ctx = [(lbl, s["metrics"][k]) for k, lbl in CONTEXT if k in s["metrics"]]
    if ctx:
        out.append("\ndesign:")
        for lbl, v in ctx:
            out.append("  %-32s %s" % (lbl, v))

    if not s["metrics"]:
        out.append(
            "\nNo metrics found. Either the run died before any step wrote metrics, or "
            "this is not an OpenLane 2 run directory."
        )
    if s["warnings"]:
        out.append("\nwarning.log (last lines):")
        out.extend("  " + ln for ln in s["warnings"])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("run", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.run.is_dir():
        print("no such directory: %s" % args.run, file=sys.stderr)
        return 2

    run = newest_run(args.run)
    s = summarise(run)
    print(json.dumps(s, indent=2) if args.json else render(s))
    return 1 if (s["violations"] or not s["completed"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
