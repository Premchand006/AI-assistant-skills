#!/usr/bin/env python3
"""Structural gate for every skill in skills/.

This checks the things that can be checked mechanically: frontmatter shape,
the documented size budgets, house style, and whether the files a SKILL.md
points at actually exist. It says nothing about whether a skill *helps* --
that is what evals/eval_runner.py is for.

Budgets enforced here (sources in docs/authoring-skills.md):
  * SKILL.md body <= 500 lines and <= ~5000 tokens
  * description <= 1024 characters
  * description + when_to_use <= 1536 characters (Claude Code listing truncation)

Exit code 0 = all skills pass. 1 = at least one error.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_BODY_LINES = 500
MAX_BODY_TOKENS = 5000
MAX_DESCRIPTION_CHARS = 1024
MAX_LISTING_CHARS = 1536
MAX_NAME_CHARS = 64

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# All-caps imperatives: skill-creator flags these; prefer explaining the why.
SHOUTED_RE = re.compile(
    r"(?<![A-Za-z])(MUST|ALWAYS|NEVER|CRITICAL|IMPORTANT|DO NOT)(?![A-Za-z])"
)
LOCAL_LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)\s]+)\)")
# Paths mentioned in prose or commands, e.g. scripts/lint_rtl.sh or ./scripts/x.sh
BARE_PATH_RE = re.compile(r"(?<![\w-])(?:\./)?((?:references|scripts|assets)/[A-Za-z0-9_./-]+)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# Generated or editor files that are not part of the skill.
IGNORED_BUNDLED = ("__pycache__", ".pyc", ".pyo", ".DS_Store", ".gitkeep")

TRIGGER_HINTS = ("use when", "use this when", "when the user", "when asked", "when working")


def estimate_tokens(text: str) -> int:
    """Rough token estimate. Deliberately conservative: ~4 chars per token."""
    return (len(text) + 3) // 4


@dataclass
class Result:
    skill: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def split_frontmatter(text: str):
    """Return (frontmatter_text, body_text). Empty frontmatter if absent."""
    if not text.startswith("---"):
        return "", text
    lines = text.splitlines(keepends=True)
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return "".join(lines[1:i]), "".join(lines[i + 1 :])
    return "", text


def parse_frontmatter(fm_text: str) -> dict:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(fm_text) or {}
        if not isinstance(data, dict):
            raise ValueError("frontmatter is not a mapping")
        return data
    except ImportError:
        pass
    # Dependency-free fallback: flat "key: value" plus simple block scalars.
    data = {}
    key = None
    buf = []
    for raw in fm_text.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if m:
            if key is not None:
                data[key] = "\n".join(buf).strip()
                buf = []
            key, value = m.group(1), m.group(2).strip()
            if value in ("|", ">", "|-", ">-"):
                continue
            data[key] = value.strip("'\"")
            key = None
        elif key is not None:
            buf.append(raw.strip())
    if key is not None:
        data[key] = "\n".join(buf).strip()
    return data


def check_skill(skill_dir: Path) -> Result:
    res = Result(skill=skill_dir.name)
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        res.errors.append("missing SKILL.md")
        return res

    text = skill_md.read_text(encoding="utf-8")
    fm_text, body = split_frontmatter(text)
    if not fm_text.strip():
        res.errors.append("missing YAML frontmatter delimited by --- lines")
        return res

    try:
        fm = parse_frontmatter(fm_text)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure verbatim
        res.errors.append("frontmatter does not parse as YAML: %s" % exc)
        return res

    # --- name -------------------------------------------------------------
    name = str(fm.get("name", "")).strip()
    if not name:
        res.errors.append("frontmatter is missing 'name'")
    else:
        if not NAME_RE.match(name):
            res.errors.append("name %r is not lowercase-kebab-case" % name)
        if len(name) > MAX_NAME_CHARS:
            res.errors.append("name is %d chars (max %d)" % (len(name), MAX_NAME_CHARS))
        if name != skill_dir.name:
            res.errors.append(
                "name %r does not match directory %r" % (name, skill_dir.name)
            )

    # --- description ------------------------------------------------------
    description = str(fm.get("description", "")).strip()
    when_to_use = str(fm.get("when_to_use", "")).strip()
    if not description:
        res.errors.append("frontmatter is missing 'description'")
    else:
        if len(description) > MAX_DESCRIPTION_CHARS:
            res.errors.append(
                "description is %d chars (max %d)" % (len(description), MAX_DESCRIPTION_CHARS)
            )
        listing = len(description) + len(when_to_use)
        if listing > MAX_LISTING_CHARS:
            res.errors.append(
                "description + when_to_use is %d chars (max %d)" % (listing, MAX_LISTING_CHARS)
            )
        low = description.lower()
        if not any(hint in low for hint in TRIGGER_HINTS):
            res.errors.append(
                "description does not say when to use the skill; add a 'Use when ...' clause"
            )
        if "TODO" in description:
            res.errors.append(
                "description still contains a TODO placeholder from new_skill.py"
            )
        if len(description) < 80:
            res.warnings.append(
                "description is only %d chars; short descriptions trigger poorly" % len(description)
            )

    for extra in ("license", "version"):
        if extra not in fm:
            res.warnings.append("frontmatter has no '%s' field" % extra)

    # --- body budgets -----------------------------------------------------
    body_lines = body.strip("\n").count("\n") + 1 if body.strip() else 0
    if body_lines > MAX_BODY_LINES:
        res.errors.append("SKILL.md body is %d lines (max %d)" % (body_lines, MAX_BODY_LINES))
    tokens = estimate_tokens(body)
    if tokens > MAX_BODY_TOKENS:
        res.errors.append("SKILL.md body is ~%d tokens (max %d)" % (tokens, MAX_BODY_TOKENS))
    elif tokens > int(MAX_BODY_TOKENS * 0.85):
        res.warnings.append(
            "SKILL.md body is ~%d tokens; approaching the %d budget" % (tokens, MAX_BODY_TOKENS)
        )

    # --- house style ------------------------------------------------------
    # Inline code spans are exempt: a skill has to be able to quote the thing
    # it is telling you not to write.
    for lineno, line in enumerate(body.splitlines(), start=1):
        for m in SHOUTED_RE.finditer(INLINE_CODE_RE.sub(" ", line)):
            res.errors.append(
                "line %d: all-caps imperative %r; state the reason instead "
                "(see docs/authoring-skills.md)" % (lineno, m.group(1))
            )

    # --- referenced files exist -------------------------------------------
    referenced = set()
    for m in LOCAL_LINK_RE.finditer(body):
        referenced.add(m.group(1).split("#", 1)[0])
    for m in BARE_PATH_RE.finditer(body):
        referenced.add(m.group(1).rstrip(".,;:)"))
    for rel in sorted(referenced):
        if not rel or rel.endswith("/"):
            continue
        if not (skill_dir / rel).exists():
            res.errors.append("SKILL.md references %s which does not exist" % rel)

    # --- bundled files are reachable --------------------------------------
    for sub in ("references", "scripts"):
        d = skill_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            rel = f.relative_to(skill_dir).as_posix()
            if f.is_dir() or any(ig in rel for ig in IGNORED_BUNDLED):
                continue
            if rel not in referenced:
                res.warnings.append("%s is bundled but never referenced from SKILL.md" % rel)

    # --- evals exist ------------------------------------------------------
    eval_file = skill_dir / "evals" / "eval.yaml"
    if not eval_file.is_file():
        res.errors.append("missing evals/eval.yaml (every skill ships with evals)")
    else:
        res.errors.extend(check_eval_file(eval_file))
    return res


def check_eval_file(path: Path) -> list:
    try:
        import yaml  # type: ignore
    except ImportError:
        return []  # nothing to say without a parser; eval_runner.py requires PyYAML
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return ["evals/eval.yaml does not parse: %s" % exc]
    errors = []
    if not isinstance(data, dict):
        return ["evals/eval.yaml is not a mapping"]
    if "skill" not in data:
        errors.append("evals/eval.yaml is missing 'skill'")
    discovery = data.get("discovery") or {}
    if not discovery.get("should_trigger"):
        errors.append("evals/eval.yaml has no discovery.should_trigger prompts")
    if not discovery.get("should_not_trigger"):
        errors.append(
            "evals/eval.yaml has no discovery.should_not_trigger prompts "
            "(adversarial discovery is how false positives get caught)"
        )
    cases = data.get("usefulness") or []
    if not cases:
        errors.append("evals/eval.yaml has no usefulness cases")
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append("usefulness[%d] is not a mapping" % i)
            continue
        for key in ("id", "prompt", "graders"):
            if key not in case:
                errors.append("usefulness[%d] is missing '%s'" % (i, key))
    if "TODO" in path.read_text(encoding="utf-8"):
        errors.append(
            "evals/eval.yaml still contains TODO placeholders from new_skill.py; "
            "fill in the cases before the skill ships"
        )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--skills-dir", default="skills", type=Path)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()

    root = Path(args.skills_dir)
    if not root.is_dir():
        print("no such directory: %s" % root, file=sys.stderr)
        return 2

    skill_dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not skill_dirs:
        print("no skills found under %s" % root, file=sys.stderr)
        return 2

    results = [check_skill(d) for d in skill_dirs]
    failed = 0
    for r in results:
        if args.strict and r.warnings:
            r.errors.extend("(strict) " + w for w in r.warnings)
            r.warnings = []
        if r.ok:
            if not args.quiet:
                suffix = "  (%d warning(s))" % len(r.warnings) if r.warnings else ""
                print("PASS  %s%s" % (r.skill, suffix))
                for w in r.warnings:
                    print("      warn: %s" % w)
        else:
            failed += 1
            print("FAIL  %s" % r.skill)
            for e in r.errors:
                print("      error: %s" % e)
            for w in r.warnings:
                print("      warn:  %s" % w)

    print("\n%d/%d skills passed structural validation" % (len(results) - failed, len(results)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
