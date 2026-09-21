#!/usr/bin/env python3
"""Find clock-domain crossings in RTL and check how they are synchronised.

Infers each signal's clock domain from the always blocks that write it,
propagates domains through combinational logic, and reports every signal read
in one domain that was written in another. For each crossing it then looks for
a two-flop synchroniser on the destination side and reports what is missing.

CDC bugs do not show up in RTL simulation and do not show up in static timing
analysis. They show up as a machine that hangs once a week. This catches the
structural cases before silicon.

Usage:
    python cdc_scan.py rtl/*.sv [--json] [--fail-on error|warn]
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

SEVERITIES = ("error", "warn", "info")
SOURCE_SUFFIXES = (".v", ".sv")
RESET_RE = re.compile(r"(rst|reset|clr|clear)", re.IGNORECASE)
IDENT_RE = re.compile(r"\b([A-Za-z_]\w*)\b")

VERILOG_WORDS = {
    "if", "else", "begin", "end", "case", "casez", "casex", "endcase", "default",
    "for", "while", "posedge", "negedge", "or", "and", "not", "assign", "always",
    "always_ff", "always_comb", "always_latch", "wire", "reg", "logic", "bit",
    "input", "output", "inout", "parameter", "localparam", "module", "endmodule",
    "signed", "unsigned", "int", "integer", "genvar", "generate", "endgenerate",
    "function", "endfunction", "task", "endtask", "return", "break", "continue",
    "unique", "priority", "typedef", "enum", "struct", "packed", "const",
}


# --------------------------------------------------------------------------
# lexing (same approach as rtl-verilog-lint/scripts/check_synthesizable.py)
# --------------------------------------------------------------------------


def strip_comments(text: str) -> str:
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


def identifiers(expr: str) -> set:
    names = set()
    for m in IDENT_RE.finditer(expr):
        name = m.group(1)
        if name in VERILOG_WORDS or re.match(r"^\d", name):
            continue
        names.add(name)
    return names


# --------------------------------------------------------------------------
# structure
# --------------------------------------------------------------------------


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


def find_modules(src: str):
    for m in re.finditer(r"\bmodule\s+(\w+)", src):
        end = re.search(r"\bendmodule\b", src, 0) if False else None
        e = re.compile(r"\bendmodule\b").search(src, m.end())
        yield m.group(1), m.start(), (e.end() if e else len(src))


def match_sensitivity(src: str, pos: int):
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
            depth += 1 if m.group(1) == "begin" else -1
            if depth == 0:
                return src[i : m.end()], m.end()
            j = m.end()
    j = src.find(";", i)
    return (src[i : j + 1], j + 1) if j != -1 else (src[i:], len(src))


def widths(body: str) -> dict:
    """signal name -> declared width text ('' for 1 bit)."""
    out = {}
    decl = re.compile(
        r"\b(?:input|output|inout|wire|reg|logic|bit)\b(?:\s+(?:wire|reg|logic|bit))?"
        r"(?:\s+signed|\s+unsigned)?\s*(\[[^\]]*\])?\s*([A-Za-z_]\w*)"
    )
    for m in decl.finditer(body):
        out.setdefault(m.group(2), m.group(1) or "")
    return out


def is_multibit(width_text: str) -> bool:
    if not width_text:
        return False
    m = re.match(r"\[\s*(\d+)\s*:\s*(\d+)\s*\]", width_text)
    if m:
        return int(m.group(1)) != int(m.group(2))
    return True  # parameterised width: treat as multi-bit


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------


def split_statements(body: str) -> list:
    """Crude statement split that is good enough for assignment extraction."""
    return [s for s in re.split(r";", body) if s.strip()]


ASSIGN_RE = re.compile(
    r"(?:^|;|\)|\bbegin\b|\belse\b|:)\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(<=|=)(?![=<>])([^;]*)",
    re.MULTILINE,
)


def analyse_module(src, mstart, mend, mod_name, fname, findings):
    body = src[mstart:mend]
    decl_width = widths(body)

    seq_blocks = []   # {clock, resets, writes:set, reads:set, pairs:[(lhs,rhs)], pos}
    comb_deps = {}    # target -> set(sources)
    comb_pos = {}

    # continuous assignments
    for m in re.finditer(r"\bassign\b([^;]*);", body):
        stmt = m.group(1)
        if "=" not in stmt:
            continue
        lhs, rhs = stmt.split("=", 1)
        target = (identifiers(lhs) or {None}).pop() if identifiers(lhs) else None
        if target:
            comb_deps.setdefault(target, set()).update(identifiers(rhs))
            comb_pos.setdefault(target, mstart + m.start())

    # always blocks
    for m in re.finditer(r"\b(always_ff|always_comb|always_latch|always)\b", body):
        sens, after = match_sensitivity(body, m.end())
        blk, _ = extract_block(body, after)
        edges = re.findall(r"\b(?:posedge|negedge)\s+(\w+)", sens or "")
        pairs = []
        for a in ASSIGN_RE.finditer(blk):
            pairs.append((a.group(1), a.group(3)))
        if edges:
            clocks = [e for e in edges if not RESET_RE.search(e)]
            resets = [e for e in edges if RESET_RE.search(e)]
            clock = clocks[0] if clocks else edges[0]
            reads = set()
            for _, rhs in pairs:
                reads |= identifiers(rhs)
            for cond in re.finditer(r"\b(?:if|case[zx]?)\s*\(([^)]*)\)", blk):
                reads |= identifiers(cond.group(1))
            seq_blocks.append({
                "clock": clock, "resets": resets, "pos": mstart + m.start(),
                "pairs": pairs, "reads": reads,
                "writes": set(p[0] for p in pairs),
                "multi_clock": len(clocks) > 1,
            })
        else:
            for lhs, rhs in pairs:
                comb_deps.setdefault(lhs, set()).update(identifiers(rhs))
                comb_pos.setdefault(lhs, mstart + m.start())

    if len(set(b["clock"] for b in seq_blocks)) < 2:
        _check_reset_sync(seq_blocks, mod_name, fname, src, findings)
        return

    # signal -> the clock domain that writes it
    write_domain = {}
    for b in seq_blocks:
        for w in b["writes"]:
            write_domain.setdefault(w, set()).add(b["clock"])

    memo = {}

    def domains_of(sig, seen=None):
        if sig in write_domain:
            return set(write_domain[sig])
        if sig in memo:
            return memo[sig]
        seen = seen or set()
        if sig in seen or sig not in comb_deps:
            return set()
        seen.add(sig)
        out = set()
        for dep in comb_deps[sig]:
            out |= domains_of(dep, seen)
        memo[sig] = out
        return out

    # two-flop synchronisers present in each domain:
    # stage1 <= src (bare identifier), stage2 <= stage1
    direct = {}   # (clock, dest) -> src
    for b in seq_blocks:
        for lhs, rhs in b["pairs"]:
            names = identifiers(rhs)
            if len(names) == 1 and re.match(r"^\s*[A-Za-z_]\w*\s*$", rhs):
                direct[(b["clock"], lhs)] = names.pop()

    def synchronised(clock, src):
        """Is src captured by >= 2 chained flops in this clock domain?"""
        firsts = [d for (c, d), s in direct.items() if c == clock and s == src]
        for f in firsts:
            if any(c == clock and s == f for (c, d), s in direct.items()):
                return True
        return False

    def first_stage_only(clock, src):
        return any(c == clock and s == src for (c, d), s in direct.items())

    reported = set()
    for b in seq_blocks:
        if b["multi_clock"]:
            findings.append(Finding(
                "error", "multi-clock-block", fname, line_of(src, b["pos"]),
                "one always block is clocked by more than one clock in '%s'" % mod_name,
                "a flop has one clock; split the block so each clock owns its own logic",
            ))
        dest = b["clock"]
        for sig in sorted(b["reads"]):
            srcs = domains_of(sig)
            foreign = {d for d in srcs if d != dest}
            if not foreign:
                continue
            key = (mod_name, sig, dest)
            if key in reported:
                continue
            reported.add(key)
            src_dom = ", ".join(sorted(foreign))
            multibit = is_multibit(decl_width.get(sig, ""))

            if not synchronised(dest, sig):
                if first_stage_only(dest, sig):
                    findings.append(Finding(
                        "error", "single-flop-sync", fname, line_of(src, b["pos"]),
                        "'%s' crosses %s -> %s through one flop" % (sig, src_dom, dest),
                        "one flop still goes metastable; the second flop is what gives the "
                        "first one time to settle. Add a second stage.",
                    ))
                else:
                    findings.append(Finding(
                        "error", "unsynchronised-crossing", fname, line_of(src, b["pos"]),
                        "'%s' is written in domain %s and read in domain %s with no synchroniser"
                        % (sig, src_dom, dest),
                        "add a two-flop synchroniser in the %s domain, or a handshake or "
                        "async FIFO if the signal carries data" % dest,
                    ))
            elif multibit:
                findings.append(Finding(
                    "error", "multibit-2ff", fname, line_of(src, b["pos"]),
                    "multi-bit signal '%s' crosses %s -> %s through a two-flop synchroniser"
                    % (sig, src_dom, dest),
                    "the bits settle independently, so the destination can sample a value "
                    "that never existed; use gray coding, a handshake, or an async FIFO",
                ))
            else:
                findings.append(Finding(
                    "info", "synchronised-crossing", fname, line_of(src, b["pos"]),
                    "'%s' crosses %s -> %s through a two-flop synchroniser"
                    % (sig, src_dom, dest),
                    "confirm the source is a registered output, not combinational logic, "
                    "and add a set_false_path or set_max_delay constraint in the SDC",
                ))

            if sig in comb_deps and sig not in write_domain:
                findings.append(Finding(
                    "warn", "combinational-source", fname, line_of(src, comb_pos.get(sig, b["pos"])),
                    "'%s' is combinational logic sampled across a domain boundary" % sig,
                    "combinational outputs glitch; register the signal in its source domain "
                    "before it crosses",
                ))

    _check_reset_sync(seq_blocks, mod_name, fname, src, findings)


def _check_reset_sync(seq_blocks, mod_name, fname, src, findings):
    reset_domains = {}
    for b in seq_blocks:
        for r in b["resets"]:
            reset_domains.setdefault(r, set()).add(b["clock"])
    for rst, clocks in reset_domains.items():
        if len(clocks) > 1:
            findings.append(Finding(
                "warn", "shared-async-reset", fname, line_of(src, seq_blocks[0]["pos"]),
                "async reset '%s' is used in %d clock domains (%s) in '%s'"
                % (rst, len(clocks), ", ".join(sorted(clocks)), mod_name),
                "an async reset released near a clock edge violates recovery/removal in "
                "whichever domain loses the race; synchronise the release per domain "
                "(async assert, sync de-assert)",
            ))


def check_file(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = strip_comments(raw)
    findings = []
    for mod_name, mstart, mend in find_modules(src):
        analyse_module(src, mstart, mend, mod_name, path.name, findings)
    return findings


# --------------------------------------------------------------------------


def collect_files(targets, excludes) -> list:
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*")) if f.suffix in SOURCE_SUFFIXES)
        elif p.is_file():
            files.append(p)
    return [f for f in files if not any(fnmatch.fnmatch(f.name, e) for e in excludes)]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("targets", nargs="+")
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
        print("\n%d file(s) scanned: %d error, %d warn, %d info"
              % (len(files), counts["error"], counts["warn"], counts["info"]))
        if not any(f.sev in ("error", "warn") for f in findings):
            print("No structural CDC problem found. This checks synchroniser structure "
                  "only; it does not prove the protocol across the boundary is correct.")

    if args.fail_on == "never":
        return 0
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.sev) <= threshold for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
