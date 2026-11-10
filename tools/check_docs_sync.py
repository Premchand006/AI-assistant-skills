#!/usr/bin/env python3
"""Fail when the public-facing docs drift from what is in the repository.

The README, llms.txt and the plugin manifests are what a visitor, a search
engine, a skills directory or an AI assistant reads first. Each one names the
skills and quotes counts; every time a skill is added those claims go stale
unless something checks them. This does.

Checks:
  - the README skill table, llms.txt and CITATION.cff name every skill in
    skills/ and nothing else
  - the counts the README quotes (skills validated, scripts compiled, eval
    cases and prompts) match what is on disk
  - the marketplace entry does not duplicate plugin.json's version,
    description or keywords (plugin.json's version wins silently; the entry's
    description and keywords hide plugin.json's), and no description quotes
    a stale skill count in words

Usage:
  python tools/check_docs_sync.py          # exit 1 on any drift
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
WORD_COUNT = re.compile(r"\b(" + "|".join(NUMBER_WORDS) + r")\s+(?:measured\s+)?skills\b", re.I)


def skill_names() -> list[str]:
    return sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())


def script_count() -> int:
    # Same globs as tools/smoke_imports.py, which prints "compiled N script(s)".
    return (len(list(ROOT.glob("skills/*/scripts/*.py")))
            + len(list(ROOT.glob("tools/*.py")))
            + len(list(ROOT.glob("evals/*.py"))))


def eval_counts(names: list[str]) -> tuple[int, int, int]:
    useful = disc = adv = 0
    for name in names:
        path = SKILLS / name / "evals" / "eval.yaml"
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        useful += len(data.get("usefulness") or [])
        discovery = data.get("discovery") or {}
        disc += len(discovery.get("should_trigger") or [])
        adv += len(discovery.get("should_not_trigger") or [])
    return useful, disc, adv


def linked_skills(text: str) -> set[str]:
    # The lookbehind keeps ".../AI-assistant-skills/blob/" from reading as a skill.
    return set(re.findall(r"(?<![\w-])skills/([a-z0-9][a-z0-9-]*)/", text))


def word_counts(text: str) -> list[tuple[str, int]]:
    return [(m.group(0), NUMBER_WORDS[m.group(1).lower()]) for m in WORD_COUNT.finditer(text)]


def main() -> int:
    names = skill_names()
    n = len(names)
    want = set(names)
    errors: list[str] = []

    def compare(label: str, got: set[str]) -> None:
        if missing := sorted(want - got):
            errors.append(f"{label}: missing {', '.join(missing)}")
        if extra := sorted(got - want):
            errors.append(f"{label}: names skills that do not exist: {', '.join(extra)}")

    # README
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    table = readme.split("## What is in it", 1)[-1].split("\n## ", 1)[0]
    compare("README skill table", linked_skills(table))

    m = re.search(r"validate_skills\.py --strict\s+#\s*(\d+)/(\d+) skills pass", readme)
    if not m or (int(m.group(1)), int(m.group(2))) != (n, n):
        errors.append(f"README: validate_skills comment should read '{n}/{n} skills pass'")

    scripts = script_count()
    m = re.search(r"smoke_imports\.py\s+#\s*(\d+) scripts compile", readme)
    if not m or int(m.group(1)) != scripts:
        errors.append(f"README: smoke_imports comment should read '{scripts} scripts compile'")

    useful, disc, adv = eval_counts(names)
    m = re.search(r"(\d+) usefulness cases, (\d+) discovery prompts\s+and\s+(\d+) adversarial", readme)
    if not m or tuple(map(int, m.groups())) != (useful, disc, adv):
        errors.append(f"README: eval totals should read '{useful} usefulness cases, "
                      f"{disc} discovery prompts and {adv} adversarial prompts'")

    for phrase, count in word_counts(readme):
        if count != n:
            errors.append(f"README: '{phrase}' but there are {n} skills")

    # llms.txt
    llms = ROOT / "llms.txt"
    if llms.is_file():
        compare("llms.txt", linked_skills(llms.read_text(encoding="utf-8")))
    else:
        errors.append("llms.txt: missing")

    # CITATION.cff keywords are free text; only check it parses and names the repo.
    cff = ROOT / "CITATION.cff"
    if cff.is_file():
        data = yaml.safe_load(cff.read_text(encoding="utf-8")) or {}
        if "AI-assistant-skills" not in str(data.get("repository-code", "")):
            errors.append("CITATION.cff: repository-code should point at the GitHub repo")

    # Plugin manifests
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    entry = next((p for p in market.get("plugins", []) if p.get("name") == plugin.get("name")), None)
    if entry is None:
        errors.append(f"marketplace.json: no plugin entry named {plugin.get('name')!r}")
    elif "version" in entry:
        # plugin.json's version silently wins over the entry's, so a second copy
        # can only ever be wrong. Keep the version in plugin.json alone.
        errors.append(f"marketplace.json: remove 'version' from the {entry['name']!r} entry; "
                      f"plugin.json ({plugin.get('version')}) takes precedence over it")
    for field in ("description", "keywords"):
        if entry and field in entry:
            errors.append(f"marketplace.json: '{field}' on the entry overrides plugin.json's; "
                          f"set it in plugin.json only")
    for label, desc in (("plugin.json", plugin.get("description", "")),
                        ("marketplace.json", (entry or {}).get("description", "")),
                        ("marketplace.json metadata", market.get("metadata", {}).get("description", ""))):
        for phrase, count in word_counts(desc):
            if count != n:
                errors.append(f"{label}: description says '{phrase}' but there are {n} skills")

    for e in errors:
        print(f"FAIL  {e}")
    if errors:
        print(f"\n{len(errors)} drift problem(s). Update the docs, not the check.")
        return 1
    print(f"docs in sync: {n} skills, {scripts} scripts, "
          f"{useful}/{disc}/{adv} usefulness/discovery/adversarial")
    return 0


if __name__ == "__main__":
    sys.exit(main())
