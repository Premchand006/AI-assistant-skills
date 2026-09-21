#!/usr/bin/env python3
"""Find the concurrency and determinism bugs that bite embedded C in the field.

Locates interrupt handlers, works out which globals they share with the rest of
the program, and reports the shares that are not safe: a missing `volatile`, a
read-modify-write on a shared variable with no critical section, a blocking or
non-reentrant call inside a handler, and a busy-wait with no timeout.

These are the bugs that pass every test on the bench and fail once a week in
the field, because they depend on when an interrupt lands.

Usage:
    python check_isr_safety.py src/ [--json] [--fail-on error|warn]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITIES = ("error", "warn", "info")
C_SUFFIXES = (".c", ".h")

# Calls that do not belong in an interrupt handler.
FORBIDDEN_IN_ISR = {
    "printf": "blocks on the UART for milliseconds and is not reentrant",
    "sprintf": "is large, slow, and may pull in the heap",
    "snprintf": "is large and slow for a handler",
    "puts": "blocks on the output stream",
    "malloc": "takes a lock and can deadlock against an allocation in main",
    "calloc": "takes a lock and can deadlock against an allocation in main",
    "realloc": "takes a lock and can deadlock against an allocation in main",
    "free": "takes a lock and can deadlock against an allocation in main",
    "HAL_Delay": "busy-waits on a tick that an equal-or-lower priority handler cannot advance",
    "delay": "busy-waits inside a handler",
    "vTaskDelay": "blocks, and blocking is not allowed in an ISR",
    "xQueueSend": "the ISR-safe variant is xQueueSendFromISR",
    "xQueueReceive": "the ISR-safe variant is xQueueReceiveFromISR",
    "xSemaphoreGive": "the ISR-safe variant is xSemaphoreGiveFromISR",
    "xSemaphoreTake": "blocks; a handler cannot wait for a semaphore",
    "strtok": "keeps state between calls and is not reentrant",
    "rand": "keeps state between calls and is not reentrant",
    "scanf": "blocks on input",
}

ISR_NAME_RE = re.compile(r"(_IRQHandler|_Handler|_ISR|_isr|_irq_handler)$")
ISR_ATTR_RE = re.compile(r"__attribute__\s*\(\s*\(\s*[^)]*interrupt[^)]*\)\s*\)")
MULTI_BYTE = re.compile(
    r"\b(uint16_t|int16_t|uint32_t|int32_t|uint64_t|int64_t|long|float|double|size_t)\b"
)


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


def strip_comments(text: str) -> str:
    out = []
    i, n = 0, len(text)
    while i < n:
        ch, nxt = text[i], (text[i + 1] if i + 1 < n else "")
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
        elif ch in "\"'":
            quote = ch
            out.append(" ")
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\":
                    out.append(" ")
                    i += 1
                if i < n:
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


FUNC_RE = re.compile(
    r"(?:^|\n)[ \t]*((?:[A-Za-z_][\w \t\*]*?))\b([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*\{"
)


def find_functions(src: str) -> list:
    """Return [{name, ret, start, body_start, body_end, body}] for definitions."""
    funcs = []
    for m in FUNC_RE.finditer(src):
        name = m.group(2)
        if name in ("if", "for", "while", "switch", "return", "sizeof", "do"):
            continue
        open_brace = src.index("{", m.end() - 1)
        depth, i = 0, open_brace
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        funcs.append({
            "name": name, "ret": m.group(1).strip(), "start": m.start(),
            "body_start": open_brace, "body_end": i, "body": src[open_brace : i + 1],
        })
    return funcs


def find_globals(src: str, funcs: list) -> dict:
    """File-scope variables -> {volatile, type, pos}."""
    spans = [(f["start"], f["body_end"]) for f in funcs]

    def inside_function(pos):
        return any(a <= pos <= b for a, b in spans)

    decl = re.compile(
        r"(?:^|\n)\s*((?:static\s+|volatile\s+|const\s+|unsigned\s+|signed\s+)*)"
        r"([A-Za-z_]\w*(?:\s*\*)?)\s+([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*(?:=[^;]*)?;"
    )
    out = {}
    for m in decl.finditer(src):
        if inside_function(m.start()):
            continue
        qualifiers, ctype, name = m.group(1) or "", m.group(2), m.group(3)
        if ctype in ("return", "typedef", "struct", "union", "enum", "extern"):
            continue
        out[name] = {
            "volatile": "volatile" in qualifiers,
            "type": (qualifiers + " " + ctype).strip(),
            "pos": m.start(3),
            "array": bool(m.group(4)),
        }
    return out


def find_while_conditions(body: str):
    """Yield (condition_text, position, is_empty_body) for each while loop.

    Done with brace matching rather than a regex because register conditions
    such as `while ((REG & BIT) == 0U);` nest parentheses.
    """
    for m in re.finditer(r"\bwhile\s*\(", body):
        depth, i = 0, m.end() - 1
        while i < len(body):
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        cond = body[m.end() : i]
        rest = body[i + 1 : i + 3].lstrip()
        yield cond, m.start(), rest.startswith(";")


def is_isr(func: dict, src: str) -> bool:
    if ISR_NAME_RE.search(func["name"]):
        return True
    head = src[max(0, func["start"] - 120) : func["body_start"]]
    return bool(ISR_ATTR_RE.search(head)) or bool(re.match(r"^ISR$", func["name"]))


def assigned_names(body: str) -> set:
    names = set()
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*(?:\+\+|--|[-+*/|&^]?=)(?!=)", body):
        names.add(m.group(1))
    for m in re.finditer(r"(?:\+\+|--)\s*([A-Za-z_]\w*)", body):
        names.add(m.group(1))
    return names


def read_names(body: str) -> set:
    return set(re.findall(r"\b([A-Za-z_]\w*)\b", body))


def check_file(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="replace")
    src = strip_comments(raw)
    name = path.name
    out = []

    def add(sev, rule, pos, msg, hint=""):
        out.append(Finding(sev, rule, name, line_of(src, pos), msg, hint))

    funcs = find_functions(src)
    globals_ = find_globals(src, funcs)
    isrs = [f for f in funcs if is_isr(f, src)]
    others = [f for f in funcs if f not in isrs]

    # --- inside handlers --------------------------------------------------
    isr_writes = {}
    for f in isrs:
        body = f["body"]
        for call in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", body):
            fn = call.group(1)
            if fn in FORBIDDEN_IN_ISR:
                add("error", "blocking-call-in-isr", f["body_start"] + call.start(),
                    "%s() called in interrupt handler %s()" % (fn, f["name"]),
                    "%s; set a flag and do the work in the main loop" % FORBIDDEN_IN_ISR[fn])

        if re.search(r"\bwhile\s*\(\s*(1|true)\s*\)", body):
            add("error", "infinite-loop-in-isr", f["body_start"],
                "unbounded loop in interrupt handler %s()" % f["name"],
                "a handler that never returns starves everything at or below its priority")

        for cond, pos, empty_body in find_while_conditions(body):
            if empty_body and not re.search(r"timeout|deadline|tries|attempts|count", cond, re.I):
                add("warn", "busy-wait-no-timeout", f["body_start"] + pos,
                    "busy-wait with no timeout in %s()" % f["name"],
                    "a peripheral that never sets the bit hangs the handler; bound the "
                    "wait and report the failure")

        if re.search(r"\b(float|double)\b", body):
            add("warn", "float-in-isr", f["body_start"],
                "floating point used in interrupt handler %s()" % f["name"],
                "on Cortex-M4F the FPU context adds 17 words to every entry; on cores "
                "without an FPU this becomes a slow software library call")

        stmts = body.count(";")
        if stmts > 40:
            add("info", "long-isr", f["body_start"],
                "handler %s() has roughly %d statements" % (f["name"], stmts),
                "long handlers add jitter to every other interrupt; defer the work")

        for w in assigned_names(body):
            if w in globals_:
                isr_writes.setdefault(w, []).append(f["name"])

    # --- sharing between handlers and the rest ----------------------------
    for var, handlers in sorted(isr_writes.items()):
        info = globals_[var]
        used_elsewhere = [f for f in others if re.search(r"\b%s\b" % re.escape(var), f["body"])]
        if not info["volatile"]:
            sev = "error" if used_elsewhere else "warn"
            add(sev, "missing-volatile", info["pos"],
                "'%s' is written by %s and is not volatile"
                % (var, ", ".join(sorted(set(handlers)))),
                "the compiler may cache it in a register or delete the read entirely, so "
                "the main loop never sees the update; declare it volatile")

        for f in used_elsewhere:
            body = f["body"]
            rmw = re.search(
                r"\b%s\s*(?:\+\+|--|[-+*/|&^]=)" % re.escape(var), body
            ) or re.search(r"\b%s\s*=\s*[^;]*\b%s\b" % (re.escape(var), re.escape(var)), body)
            protected = re.search(
                r"__disable_irq|taskENTER_CRITICAL|portENTER_CRITICAL|ATOMIC_BLOCK|"
                r"CRITICAL_SECTION|primask", body, re.I
            )
            if rmw and not protected:
                add("error", "unprotected-rmw", f["body_start"] + rmw.start(),
                    "%s() does a read-modify-write on '%s', which an interrupt also writes"
                    % (f["name"], var),
                    "volatile does not make it atomic; an interrupt between the read and "
                    "the write loses an update. Guard it with a critical section, or use "
                    "an atomic type")
            elif (
                MULTI_BYTE.search(info["type"] or "")
                and not protected
                and re.search(r"\b%s\b" % re.escape(var), body)
                and info.get("volatile")
                and re.search(r"(uint64_t|int64_t|double)", info["type"] or "")
            ):
                add("warn", "wide-shared-read", f["body_start"],
                    "%s() reads 64-bit '%s' that an interrupt writes" % (f["name"], var),
                    "a 64-bit access is not a single instruction on a 32-bit core; the "
                    "main loop can read half of an old value and half of a new one")

    # --- whole-file rules --------------------------------------------------
    for m in re.finditer(r"\b(malloc|calloc|realloc|free)\s*\(", src):
        add("warn", "dynamic-memory", m.start(),
            "%s() used" % m.group(1),
            "heap use in firmware fragments over time and gives no bound on allocation "
            "failure; static pools or fixed buffers are the usual alternative "
            "(MISRA C:2012 Dir 4.12, Rule 21.3)")

    for m in re.finditer(r"#define\s+(\w+)\(([^)]*)\)\s+([^\n]*)", src):
        body_txt, params = m.group(3), [p.strip() for p in m.group(2).split(",") if p.strip()]
        if not body_txt.strip().startswith("(") and any(
            re.search(r"[-+*/%<>&|^]", body_txt) for _ in [0]
        ):
            add("warn", "unparenthesised-macro", m.start(),
                "function-like macro %s expands to an unparenthesised expression" % m.group(1),
                "wrap the whole body and each parameter use in parentheses, or precedence "
                "at the call site changes the meaning (MISRA C:2012 Rule 20.7)")
        else:
            for p in params:
                if re.search(r"(?<![\w(])%s(?![\w)])" % re.escape(p), body_txt):
                    add("info", "unparenthesised-macro-param", m.start(),
                        "parameter '%s' of macro %s is used without parentheses"
                        % (p, m.group(1)), "")
                    break

    for m in re.finditer(r"\bgoto\b", src):
        add("info", "goto", m.start(), "goto used",
            "acceptable in MISRA C:2012 only for a forward jump to a single cleanup "
            "label in the same function (Rule 15.1 is advisory)")

    for f in funcs:
        if re.search(r"\b%s\s*\(" % re.escape(f["name"]), f["body"]):
            add("warn", "recursion", f["body_start"],
                "%s() appears to call itself" % f["name"],
                "recursion gives no static bound on stack depth, which is why MISRA C:2012 "
                "Rule 17.2 forbids it in firmware")

    return out


# --------------------------------------------------------------------------


def collect(targets) -> list:
    files = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*")) if f.suffix in C_SUFFIXES)
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
        print("no C sources matched", file=sys.stderr)
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
        print("\n%d file(s) checked: %d error, %d warn, %d info"
              % (len(files), counts["error"], counts["warn"], counts["info"]))
        print("This is a single-file heuristic pass. Run cppcheck --addon=misra and your "
              "compiler at -Wall -Wextra as well; scripts/run_static.sh does both.")

    if args.fail_on == "never":
        return 0
    threshold = SEVERITIES.index(args.fail_on)
    return 1 if any(SEVERITIES.index(f.sev) <= threshold for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
