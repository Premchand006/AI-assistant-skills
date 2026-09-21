#!/usr/bin/env python3
"""Heuristic pre-synthesis check for Verilog / SystemVerilog RTL.

Catches the mistakes that make generated RTL simulate but not synthesise, or
synthesise into something other than what the code looks like: simulation-only
constructs, latch inference, blocking assignments in sequential blocks, missing
default nettype, multiple drivers, and mixed clock edges.

This is a fast first pass, not a linter. It parses with regular expressions
after stripping comments and strings, so it can miss constructs inside macros
and it can be fooled by unusual formatting. Run verilator --lint-only and your
synthesis tool as well; scripts/lint_rtl.sh does both when they are installed.

Usage:
    python check_synthesizable.py rtl/*.v [--fail-on error|warn] [--json]
    python check_synthesizable.py rtl/ --exclude "*_tb.sv"
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

SEVERITIES = ("error", "warn", "info")
SOURCE_SUFFIXES = (".v", ".sv", ".vh", ".svh")


# --------------------------------------------------------------------------
# lexing helpers
# --------------------------------------------------------------------------


def strip_comments(text: str) -> str:
    """Blank out comments and string literals, preserving line numbering."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and nxt == "*":
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
        elif ch == '"':
            out.append(" ")
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    i += 1
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            out.append(" ")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


class Finding:
    def __init__(self, sev, rule, file, line, message, hint=""):
        self.sev, self.rule, self.file = sev, rule, file
        self.line, self.message, self.hint = line, message, hint

    def as_dict(self):
        return {
            "severity": self.sev, "rule": self.rule, "file": self.file,
            "line": self.line, "message": self.message, "hint": self.hint,
        }

    def render(self):
        s = "%s:%d: %s: [%s] %s" % (self.file, self.line, self.sev, self.rule, self.message)
        if self.hint:
            s += "\n    hint: " + self.hint
        return s


# --------------------------------------------------------------------------
# structure extraction
# --------------------------------------------------------------------------


# An assignment target: a name at the start of a statement, i.e. after a line
# break, a ';', 'begin', 'else', or a case-item colon.
ASSIGN_TARGET_RE = re.compile(
    r"(?:^|;|\)|\bbegin\b|\belse\b|:)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(<=|=)(?![=<>])",
    re.MULTILINE,
)
VERILOG_KEYWORDS = {
    "if", "else", "case", "casez", "casex", "begin", "end", "for", "while",
    "parameter", "localparam", "assign", "default", "endcase", "repeat",
}

MODULE_RE = re.compile(r"\bmodule\s+(\w+)", re.MULTILINE)
ENDMODULE_RE = re.compile(r"\bendmodule\b")
ALWAYS_RE = re.compile(r"\b(always_ff|always_comb|always_latch|always)\b")


def find_modules(src: str):
    """Yield (name, start_index, end_index) for each module body."""
    for m in MODULE_RE.finditer(src):
        end = ENDMODULE_RE.search(src, m.end())
        yield m.group(1), m.start(), (end.end() if end else len(src))


def match_sensitivity(src: str, pos: int):
    """If an @(...) follows pos, return (text, index_after). Else (None, pos)."""
    i = pos
    while i < len(src) and src[i].isspace():
        i += 1
    if i >= len(src) or src[i] != "@":
        return None, pos
    i += 1
    while i < len(src) and src[i].isspace():
        i += 1
    if i < len(src) and src[i] == "*":
        return "*", i + 1
    if i >= len(src) or src[i] != "(":
        return None, pos
    depth, start = 0, i
    while i < len(src):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                return src[start + 1 : i], i + 1
        i += 1
    return None, pos


def extract_block(src: str, pos: int):
    """Return (body_text, end_index) for the statement starting at pos."""
    i = pos
    while i < len(src) and src[i].isspace():
        i += 1
    if src.startswith("begin", i):
        depth, j = 0, i
        token = re.compile(r"\b(begin|end)\b")
        while True:
            m = token.search(src, j)
            if not m:
                return src[i:], len(src)
            if m.group(1) == "begin":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return src[i : m.end()], m.end()
            j = m.end()
    j = src.find(";", i)
    if j == -1:
        return src[i:], len(src)
    return src[i : j + 1], j + 1


def find_always_blocks(src: str, start: int, end: int):
    """Yield dicts describing each always block inside [start, end)."""
    for m in ALWAYS_RE.finditer(src, start, end):
        kind = m.group(1)
        sens, after = match_sensitivity(src, m.end())
        body, body_end = extract_block(src, after)
        yield {
            "kind": kind,
            "sens": sens,
            "body": body,
            "pos": m.start(),
            "body_pos": after,
            "end": body_end,
        }


def is_sequential(block) -> bool:
    if block["kind"] == "always_ff":
        return True
    sens = block["sens"] or ""
    return bool(re.search(r"\b(posedge|negedge)\b", sens))


def is_combinational(block) -> bool:
    if block["kind"] in ("always_comb", "always_latch"):
        return block["kind"] == "always_comb"
    sens = block["sens"]
    return sens is not None and not re.search(r"\b(posedge|negedge)\b", sens)


def looks_like_testbench(name: str, body: str) -> bool:
    if re.search(r"(^|_)(tb|test|testbench)(_|$)", name, re.IGNORECASE):
        return True
    if re.match(r"^\s*module\s+\w+\s*;", body):  # no port list at all
        return bool(re.search(r"\binitial\b", body))
    return False


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------


def check_file(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = strip_comments(raw)
    name = path.name
    findings = []

    def add(sev, rule, pos, message, hint=""):
        findings.append(Finding(sev, rule, name, line_of(src, pos), message, hint))

    if not re.search(r"`default_nettype\s+none", src):
        add(
            "warn", "default-nettype", 0,
            "file does not set `default_nettype none",
            "a typo in a signal name silently becomes a 1-bit wire without it; "
            "add `default_nettype none at the top and `default_nettype wire at the bottom",
        )

    for mod_name, mstart, mend in find_modules(src):
        body = src[mstart:mend]
        if looks_like_testbench(mod_name, body):
            continue

        # --- simulation-only constructs ----------------------------------
        for m in re.finditer(r"#\s*(\d+|\w+|\()", body):
            # #(...) directly after a module/instance name is a parameter list
            before = body[max(0, m.start() - 40) : m.start()]
            if re.search(r"\w\s*$", before) and m.group(1) == "(":
                continue
            add(
                "error", "delay-control", mstart + m.start(),
                "delay control '#' in synthesisable module '%s'" % mod_name,
                "synthesis ignores or rejects delays; model timing with clocked logic instead",
            )
        for m in re.finditer(r"\b(initial)\b", body):
            add(
                "error", "initial-block", mstart + m.start(),
                "initial block in synthesisable module '%s'" % mod_name,
                "use a reset value in the sequential block; FPGA-only initial state belongs "
                "behind `ifdef and does not carry to ASIC flows",
            )
        for m in re.finditer(r"\b(real|realtime|time|shortreal)\s+\w+", body):
            add(
                "error", "unsynthesisable-type", mstart + m.start(),
                "type '%s' is simulation-only" % m.group(1),
                "use fixed-point on integral types for hardware",
            )
        for m in re.finditer(r"\$(display|write|monitor|finish|stop|fopen|fwrite|random|time)\b", body):
            add(
                "warn", "system-task", mstart + m.start(),
                "system task $%s in module '%s'" % (m.group(1), mod_name),
                "guard debug output with `ifndef SYNTHESIS so synthesis never sees it",
            )
        for m in re.finditer(r"\bforce\b|\brelease\b|\bfork\b|\bwait\b", body):
            add(
                "error", "unsynthesisable-stmt", mstart + m.start(),
                "'%s' is not synthesisable" % m.group(0),
                "restructure as an FSM",
            )

        # --- per-always-block rules --------------------------------------
        drivers = {}
        for blk in find_always_blocks(src, mstart, mend):
            bbody, bpos = blk["body"], blk["body_pos"]
            seq, comb = is_sequential(blk), is_combinational(blk)

            if seq:
                for m in re.finditer(r"(?<![<>=!+\-*/%&|^~])=(?!=)", bbody):
                    seg = bbody[max(0, m.start() - 60) : m.start()]
                    if re.search(r"\b(parameter|localparam|for|automatic)\b[^;]*$", seg):
                        continue
                    add(
                        "error", "blocking-in-sequential", bpos + m.start(),
                        "blocking assignment in a clocked block in '%s'" % mod_name,
                        "use <= in clocked blocks; mixing = there creates simulation/synthesis "
                        "mismatches that depend on statement order",
                    )
                    break
                sens = blk["sens"] or ""
                edges = re.findall(r"\b(?:posedge|negedge)\s+(\w+)", sens)
                bare = [
                    t.strip()
                    for t in re.split(r"\bor\b|,", sens)
                    if t.strip() and not re.search(r"\b(posedge|negedge)\b", t)
                ]
                if bare:
                    add(
                        "error", "mixed-sensitivity", blk["pos"],
                        "clocked block lists level-sensitive signal(s) %s" % ", ".join(bare),
                        "every term in a clocked sensitivity list needs posedge or negedge; "
                        "write always @(posedge clk or negedge rst_n)",
                    )
                if len(edges) > 2:
                    add(
                        "warn", "multi-clock-block", blk["pos"],
                        "clocked block is sensitive to %d edges (%s)" % (len(edges), ", ".join(edges)),
                        "one clock plus at most one async reset per block keeps the netlist "
                        "mappable to a single flop type",
                    )
                if len(edges) == 2:
                    reset_like = re.compile(r"(rst|reset|clr|clear)", re.IGNORECASE)
                    if not any(reset_like.search(e) for e in edges[1:]):
                        add(
                            "warn", "two-clock-block", blk["pos"],
                            "clocked block has two edges and neither looks like a reset (%s)"
                            % ", ".join(edges),
                            "a block clocked by two clocks is a CDC hazard; split it",
                        )

            if comb:
                if re.search(r"<=", bbody):
                    add(
                        "warn", "nonblocking-in-combinational", bpos,
                        "non-blocking assignment in a combinational block in '%s'" % mod_name,
                        "use = in combinational blocks; <= there delays the update by a delta "
                        "cycle and can hide feedback bugs",
                    )
                sens = blk["sens"] or ""
                if blk["kind"] == "always" and sens not in ("*", "") and "*" not in sens:
                    add(
                        "warn", "incomplete-sensitivity", blk["pos"],
                        "combinational block uses an explicit sensitivity list (%s)" % sens.strip(),
                        "always_comb, or always @(*), cannot drift out of date when you add "
                        "a term to the expression",
                    )
                findings.extend(_latch_checks(bbody, bpos, mod_name, name, src))

            for m in ASSIGN_TARGET_RE.finditer(bbody):
                target = m.group(1)
                if target in VERILOG_KEYWORDS:
                    continue
                drivers.setdefault(target, set()).add(blk["pos"])

        for sig, blocks in drivers.items():
            if len(blocks) > 1:
                add(
                    "error", "multiple-drivers", min(blocks),
                    "signal '%s' is assigned in %d different always blocks" % (sig, len(blocks)),
                    "a net driven from two procedural blocks is a short in synthesis; "
                    "merge them or split the signal",
                )

        for m in re.finditer(r"[/%]\s*(?!\d*'|\s*[248]\b|\s*16\b|\s*32\b)(\w+)", body):
            if re.match(r"^\d+$", m.group(1)) or m.group(1).isidentifier():
                add(
                    "info", "divider", mstart + m.start(),
                    "division or modulo by a non-power-of-two ('%s')" % m.group(1),
                    "synthesised dividers are large and slow; use a shift, a reciprocal "
                    "multiply, or a multi-cycle divider block",
                )
                break
    return findings


def _latch_checks(bbody: str, bpos: int, mod_name: str, fname: str, src: str) -> list:
    """Flag case statements without default inside combinational logic."""
    out = []
    for m in re.finditer(r"\b(case|casez|casex)\b", bbody):
        endm = re.search(r"\bendcase\b", bbody[m.end() :])
        stop = m.end() + (endm.end() if endm else len(bbody) - m.end())
        chunk = bbody[m.start() : stop]
        if not re.search(r"\bdefault\s*:", chunk):
            out.append(
                Finding(
                    "error", "latch-from-case", fname, line_of(src, bpos + m.start()),
                    "combinational %s in '%s' has no default branch" % (m.group(1), mod_name),
                    "an unassigned branch infers a latch; add default: with an assignment to "
                    "every output of this block",
                )
            )
    return out


# --------------------------------------------------------------------------


def collect_files(targets, excludes) -> list:
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*")) if f.suffix in SOURCE_SUFFIXES)
        elif p.is_file():
            files.append(p)
    keep = []
    for f in files:
        if any(fnmatch.fnmatch(f.name, pat) for pat in excludes):
            continue
        keep.append(f)
    return keep


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("targets", nargs="+", help="RTL files or directories")
    ap.add_argument("--exclude", action="append", default=["*_tb.v", "*_tb.sv", "tb_*.v", "tb_*.sv"])
    ap.add_argument("--fail-on", choices=("error", "warn", "info", "never"), default="error")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    files = collect_files(args.targets, args.exclude)
    if not files:
        print("no RTL files matched", file=sys.stderr)
        return 2

    findings = []
    for f in files:
        findings.extend(check_file(f))
    findings.sort(key=lambda f: (SEVERITIES.index(f.sev), f.file, f.line))

    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        for f in findings:
            print(f.render())
        counts = {s: sum(1 for f in findings if f.sev == s) for s in SEVERITIES}
        print(
            "\n%d file(s) checked: %d error, %d warn, %d info"
            % (len(files), counts["error"], counts["warn"], counts["info"])
        )

    if args.fail_on == "never":
        return 0
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.sev) <= threshold for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
