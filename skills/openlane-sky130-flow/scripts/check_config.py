#!/usr/bin/env python3
"""Validate an OpenLane 2 config.json before starting a run.

An RTL-to-GDSII run costs minutes to hours. Most failed runs die in the first
minute on something a file check would have caught: a path that does not
resolve, a clock port that is not in the RTL, a PDK name that is not fully
qualified, or a utilisation target that cannot place.

Usage:
    python check_config.py path/to/config.json [--pdk-root ~/.volare] [--json]

Exit 0 when nothing above warning level is found, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Fully qualified PDK variants. "sky130" alone is a family, not a variant, and
# OpenLane rejects it.
KNOWN_PDKS = {"sky130A", "sky130B", "gf180mcuA", "gf180mcuB", "gf180mcuC", "gf180mcuD"}
REQUIRED = ("DESIGN_NAME", "VERILOG_FILES", "CLOCK_PORT", "CLOCK_PERIOD")
SOURCE_SUFFIXES = (".v", ".sv")


class Issue:
    def __init__(self, sev, key, message, hint=""):
        self.sev, self.key, self.message, self.hint = sev, key, message, hint

    def as_dict(self):
        return {"severity": self.sev, "key": self.key, "message": self.message, "hint": self.hint}

    def render(self):
        s = "%-7s %-22s %s" % (self.sev, self.key, self.message)
        if self.hint:
            s += "\n        hint: " + self.hint
        return s


def resolve(value: str, config_dir: Path, pdk_root: Path = None):
    """Resolve OpenLane's dir::, pdk_dir:: and refg:: path prefixes."""
    if value.startswith("dir::"):
        return (config_dir / value[len("dir::") :]).resolve()
    if value.startswith("pdk_dir::"):
        if pdk_root is None:
            return None
        return (pdk_root / value[len("pdk_dir::") :]).resolve()
    if value.startswith("refg::"):
        return None  # glob against a remote ref; not checkable offline
    p = Path(value)
    return p if p.is_absolute() else (config_dir / p).resolve()


def read_rtl_ports(files) -> set:
    """Collect port names declared in the given RTL files (best effort)."""
    ports = set()
    decl = re.compile(
        r"\b(?:input|output|inout)\b(?:\s+(?:wire|reg|logic|bit))?"
        r"(?:\s+signed)?(?:\s*\[[^\]]*\])?\s*([A-Za-z_]\w*)"
    )
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in decl.finditer(text):
            ports.add(m.group(1))
    return ports


def check(config_path: Path, pdk_root: Path = None) -> list:
    issues = []

    def add(sev, key, msg, hint=""):
        issues.append(Issue(sev, key, msg, hint))

    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [Issue("error", "config.json", "not valid JSON: %s" % exc,
                      "OpenLane configs are strict JSON: no trailing commas, no comments")]
    if not isinstance(cfg, dict):
        return [Issue("error", "config.json", "top level is not an object")]

    config_dir = config_path.parent

    # --- meta -------------------------------------------------------------
    meta = cfg.get("meta") or {}
    if not meta:
        add("warn", "meta", "no meta block",
            'add {"meta": {"version": 2}} so the file is read as an OpenLane 2 config')
    elif meta.get("version") != 2:
        add("warn", "meta.version", "version is %r, expected 2" % meta.get("version"),
            "OpenLane 2 reads version 1 files in a compatibility mode that resolves "
            "paths differently")

    # --- required keys ----------------------------------------------------
    for key in REQUIRED:
        if key not in cfg:
            add("error", key, "missing",
                "the Classic flow cannot start without it")

    design = cfg.get("DESIGN_NAME")
    if design and not re.match(r"^[A-Za-z_]\w*$", str(design)):
        add("error", "DESIGN_NAME", "%r is not a valid Verilog identifier" % design)

    # --- source files -----------------------------------------------------
    rtl_files = []
    vfiles = cfg.get("VERILOG_FILES")
    if isinstance(vfiles, str):
        vfiles = [vfiles]
    for entry in vfiles or []:
        if not isinstance(entry, str):
            add("error", "VERILOG_FILES", "entry %r is not a string" % entry)
            continue
        if not entry.startswith(("dir::", "pdk_dir::", "refg::", "/")):
            add("warn", "VERILOG_FILES", "%r has no dir:: prefix" % entry,
                "a bare relative path resolves against the working directory, not the "
                "config file, so the run breaks when started from elsewhere; write "
                "dir::%s" % entry)
        target = resolve(entry, config_dir, pdk_root)
        if target is None:
            continue
        if "*" in entry:
            matches = list(target.parent.glob(target.name))
            if not matches:
                add("error", "VERILOG_FILES", "glob %r matches no file" % entry)
            rtl_files.extend(matches)
        elif not target.exists():
            add("error", "VERILOG_FILES", "%s does not exist" % target)
        else:
            rtl_files.append(target)

    if vfiles is not None and not vfiles:
        add("error", "VERILOG_FILES", "empty list")

    # --- clock ------------------------------------------------------------
    clock_port = cfg.get("CLOCK_PORT")
    period = cfg.get("CLOCK_PERIOD")
    if period is not None:
        try:
            p = float(period)
            if p <= 0:
                add("error", "CLOCK_PERIOD", "must be positive, got %r" % period)
            elif p < 1:
                add("warn", "CLOCK_PERIOD", "%s ns is above 1 GHz" % period,
                    "sky130 designs on the open flow rarely close much below 10 ns; "
                    "confirm this is intentional")
        except (TypeError, ValueError):
            add("error", "CLOCK_PERIOD", "not a number: %r" % period)
        if isinstance(period, str):
            add("warn", "CLOCK_PERIOD", "given as a string",
                "OpenLane wants a number; %s not \"%s\"" % (period, period))

    if clock_port and rtl_files:
        ports = read_rtl_ports(rtl_files)
        for name in str(clock_port).split():
            if ports and name not in ports:
                add("error", "CLOCK_PORT", "%r is not a port of any listed RTL file" % name,
                    "synthesis will run unconstrained and every path will look like it "
                    "passes; ports found: %s"
                    % ", ".join(sorted(ports)[:8]))

    if "CLOCK_NET" in cfg and cfg.get("CLOCK_NET") != clock_port:
        add("info", "CLOCK_NET", "differs from CLOCK_PORT",
            "only needed when the clock enters through a pad or a gate")

    # --- floorplan --------------------------------------------------------
    util = cfg.get("FP_CORE_UTIL")
    if util is None:
        if "DIE_AREA" not in cfg:
            add("warn", "FP_CORE_UTIL", "not set and no DIE_AREA given",
                "the flow falls back to a default utilisation that is often wrong for "
                "the design; set FP_CORE_UTIL (35-55 is a workable starting range)")
    else:
        try:
            u = float(util)
            if not 1 <= u <= 99:
                add("error", "FP_CORE_UTIL", "%s is outside 1-99" % util)
            elif u > 65:
                add("warn", "FP_CORE_UTIL", "%s is high" % util,
                    "above roughly 60 the router starts failing on sky130; start near 40 "
                    "and tighten once the design closes")
        except (TypeError, ValueError):
            add("error", "FP_CORE_UTIL", "not a number: %r" % util)

    if "DIE_AREA" in cfg and "FP_SIZING" not in cfg:
        add("warn", "FP_SIZING", "DIE_AREA is set without FP_SIZING",
            'DIE_AREA is only honoured when FP_SIZING is "absolute"')

    # --- pdk --------------------------------------------------------------
    pdk = cfg.get("PDK")
    if pdk is not None:
        if pdk not in KNOWN_PDKS:
            sev = "error" if pdk in ("sky130", "gf180mcu") else "warn"
            add(sev, "PDK", "%r is not a fully qualified variant" % pdk,
                "use a variant such as sky130A, not the family name")
    std_cell = cfg.get("STD_CELL_LIBRARY")
    if std_cell and pdk and pdk.startswith("sky130") and not std_cell.startswith("sky130"):
        add("warn", "STD_CELL_LIBRARY", "%r does not look like a sky130 library" % std_cell)

    # --- other referenced files -------------------------------------------
    for key, value in cfg.items():
        if key in ("VERILOG_FILES", "meta") or not isinstance(value, str):
            continue
        if value.startswith("dir::") and "*" not in value:
            target = resolve(value, config_dir)
            if target and not target.exists():
                add("error", key, "%s does not exist" % target)

    # --- flow sanity ------------------------------------------------------
    flow = meta.get("flow")
    if isinstance(flow, list) and flow:
        if "Yosys.Synthesis" not in flow:
            add("warn", "meta.flow", "custom flow does not include Yosys.Synthesis")
        if not any(s.startswith("Magic.StreamOut") for s in flow):
            add("info", "meta.flow", "custom flow produces no GDS",
                "add Magic.StreamOut if you want a layout out of this run")

    for legacy in ("RUN_CTS", "RUN_MAGIC_DRC", "RUN_LVS", "RUN_SPEF_EXTRACTION"):
        if legacy in cfg and isinstance(flow, list):
            add("info", legacy, "RUN_* toggles are ignored when meta.flow lists steps",
                "remove the step from meta.flow instead")

    return issues


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("config", type=Path)
    ap.add_argument("--pdk-root", type=Path, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.config.is_file():
        print("no such file: %s" % args.config, file=sys.stderr)
        return 2

    issues = check(args.config, args.pdk_root)
    order = {"error": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda i: order[i.sev])

    if args.json:
        print(json.dumps([i.as_dict() for i in issues], indent=2))
    else:
        for i in issues:
            print(i.render())
        errors = sum(1 for i in issues if i.sev == "error")
        warns = sum(1 for i in issues if i.sev == "warn")
        if not issues:
            print("no problems found")
        print("\n%d error, %d warn, %d info" % (errors, warns, len(issues) - errors - warns))
        if errors:
            print("this run would fail early; fix the errors before starting it")
    return 1 if any(i.sev == "error" for i in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
