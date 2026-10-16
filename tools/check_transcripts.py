#!/usr/bin/env python3
"""Refuse transcripts that look like they contain secrets or personal data.

Transcripts under evals/transcripts/ are committed and published, and a live
eval run sends fixture contents to a model provider and writes back whatever it
says. This is the gate between the two: evals/eval_runner.py calls scan_text()
before recording a response, and CI runs this script over the committed tree.

It is a pattern scan, not a guarantee. A clean result means none of the known
shapes matched; it does not mean the text is safe to publish. A line that
legitimately trips a rule can carry the marker `transcript-scan: allow`.

Usage:
    python tools/check_transcripts.py                  # scan evals/transcripts/
    python tools/check_transcripts.py PATH... [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOW_MARKER = "transcript-scan: allow"

# (rule, pattern). Compiled once; applied line by line.
RULES = [
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("generic-secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")),
    ("home-path", re.compile(
        r"(?:/home/|/Users/|[A-Za-z]:\\Users\\)(?!<|\{|\$|user\b|username\b|you\b|me\b)[^/\\\s]+")),
    ("confidential-marker", re.compile(
        r"\b(?:CONFIDENTIAL|PROPRIETARY|INTERNAL USE ONLY|DO NOT DISTRIBUTE)\b")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

# Documentation domains (RFC 2606 / 6761) are fine in an example.
SAFE_EMAIL = re.compile(
    r"@(?:[A-Za-z0-9-]+\.)*(?:example\.(?:com|org|net)|example|test|invalid|localhost)$",
    re.IGNORECASE,
)


def scan_text(text: str) -> list:
    """Return [(rule, line_number, snippet)] for every suspicious match."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        for rule, pat in RULES:
            for m in pat.finditer(line):
                if rule == "email" and SAFE_EMAIL.search(m.group(0)):
                    continue
                snippet = m.group(0)
                # Never echo a full secret back into a log.
                if len(snippet) > 12 and rule not in ("home-path", "confidential-marker"):
                    snippet = snippet[:6] + "..." + snippet[-2:]
                hits.append((rule, n, snippet))
    return hits


def iter_files(paths: list):
    for p in paths:
        if p.is_dir():
            yield from sorted(f for f in p.rglob("*") if f.is_file() and not f.is_symlink())
        elif p.is_file():
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path,
                    default=[REPO_ROOT / "evals" / "transcripts"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    findings = []
    scanned = 0
    for f in iter_files(args.paths):
        scanned += 1
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            findings.append({"file": str(f), "line": 0, "rule": "unreadable",
                             "match": str(e)[:80]})
            continue
        for rule, line, snippet in scan_text(text):
            findings.append({"file": str(f), "line": line, "rule": rule, "match": snippet})

    if args.json:
        print(json.dumps({"scanned": scanned, "findings": findings}, indent=2))
    else:
        for x in findings:
            print("%s:%d: [%s] %s" % (x["file"], x["line"], x["rule"], x["match"]))
        print("%d file(s) scanned, %d finding(s)" % (scanned, len(findings)))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
