#!/usr/bin/env python3
"""Run the three eval families for the skills in this repo.

  usefulness  -- blind skill-on vs skill-off on the same prompt, graded by
                 deterministic checks written per case
  discovery   -- given only the frontmatter descriptions of every skill in the
                 repo, does a prompt that should select this skill select it?
  adversarial -- prompts that look superficially related but should select
                 nothing; measures the false-positive rate of the description

Runners decide where model output comes from:
  --runner replay  read recorded transcripts from evals/transcripts/ (default,
                   no API key, what CI uses so published numbers stay checkable)
  --runner cli     shell out to `claude -p` once per case
  --runner api     Anthropic Messages API (needs ANTHROPIC_API_KEY)

Usefulness scoring is deliberately dumb: each case lists graders, a case scores
pass only if every grader passes, and the headline number is
(cases passed with skill) vs (cases passed without it) over the same prompts.
Read docs/eval-methodology.md for what a pass does and does not prove.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_JUDGE_MODEL = "claude-sonnet-5"


# --------------------------------------------------------------------------
# suite loading
# --------------------------------------------------------------------------


@dataclass
class Case:
    id: str
    prompt: str
    graders: dict
    files: dict = field(default_factory=dict)
    note: str = ""


@dataclass
class Suite:
    skill: str
    path: Path
    skill_md: str
    description: str
    cases: list
    should_trigger: list
    should_not_trigger: list


def _require_yaml():
    try:
        import yaml  # type: ignore

        return yaml
    except ImportError:
        print(
            "PyYAML is required: python -m pip install -r requirements-dev.txt",
            file=sys.stderr,
        )
        raise SystemExit(2)


def frontmatter_description(skill_md_text: str) -> str:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    from validate_skills import parse_frontmatter, split_frontmatter  # type: ignore

    fm_text, _ = split_frontmatter(skill_md_text)
    fm = parse_frontmatter(fm_text)
    return str(fm.get("description", "")).strip()


def load_suites(skills_dir: Path, only: list) -> list:
    yaml = _require_yaml()
    suites = []
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        if only and d.name not in only:
            continue
        eval_path = d / "evals" / "eval.yaml"
        skill_md = d / "SKILL.md"
        if not eval_path.is_file() or not skill_md.is_file():
            continue
        data = yaml.safe_load(eval_path.read_text(encoding="utf-8")) or {}
        md = skill_md.read_text(encoding="utf-8")
        discovery = data.get("discovery") or {}
        cases = []
        for c in data.get("usefulness") or []:
            cases.append(
                Case(
                    id=c["id"],
                    prompt=c["prompt"],
                    graders=c.get("graders") or {},
                    files=c.get("files") or {},
                    note=c.get("note", ""),
                )
            )
        suites.append(
            Suite(
                skill=d.name,
                path=d,
                skill_md=md,
                description=frontmatter_description(md),
                cases=cases,
                should_trigger=list(discovery.get("should_trigger") or []),
                should_not_trigger=list(discovery.get("should_not_trigger") or []),
            )
        )
    return suites


# --------------------------------------------------------------------------
# runners
# --------------------------------------------------------------------------


class ReplayRunner:
    """Serve recorded transcripts so published results can be re-checked."""

    name = "replay"

    def __init__(self, root: Path):
        self.root = root
        self.missing = []

    def generate(self, prompt: str, system: str = "", key: str = "") -> str:
        path = self.root / (key + ".md")
        if not path.is_file():
            self.missing.append(key)
            return ""
        return path.read_text(encoding="utf-8")


class CliRunner:
    """One `claude -p` invocation per case."""

    name = "cli"

    def __init__(self, model: str, record_to: Path = None, timeout: int = 900):
        self.model = model
        self.record_to = record_to
        self.timeout = timeout

    def generate(self, prompt: str, system: str = "", key: str = "") -> str:
        full = (system + "\n\n" + prompt) if system else prompt
        cmd = ["claude", "-p", full, "--output-format", "text", "--model", self.model]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout, shell=False
        )
        out = proc.stdout.strip()
        if proc.returncode != 0 and not out:
            out = "[runner error] " + proc.stderr.strip()
        self._record(key, out)
        return out

    def _record(self, key: str, text: str):
        if not self.record_to or not key:
            return
        path = self.record_to / (key + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class ApiRunner:
    """Anthropic Messages API. Keeps the on/off comparison strictly controlled."""

    name = "api"

    def __init__(self, model: str, record_to: Path = None, max_tokens: int = 4096):
        try:
            import anthropic  # type: ignore
        except ImportError:
            print(
                "the api runner needs the anthropic SDK: python -m pip install anthropic",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set", file=sys.stderr)
            raise SystemExit(2)
        self.client = anthropic.Anthropic()
        self.model = model
        self.record_to = record_to
        self.max_tokens = max_tokens

    def generate(self, prompt: str, system: str = "", key: str = "") -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if self.record_to and key:
            path = self.record_to / (key + ".md")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return text


def build_runner(args, record_root: Path):
    if args.runner == "replay":
        return ReplayRunner(Path(args.transcripts))
    record = record_root if args.record else None
    if args.runner == "cli":
        return CliRunner(args.model, record_to=record)
    return ApiRunner(args.model, record_to=record)


# --------------------------------------------------------------------------
# graders
# --------------------------------------------------------------------------


def _as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def apply_graders(text: str, graders: dict) -> list:
    """Return a list of {name, kind, passed, detail} dicts."""
    out = []
    flags = re.IGNORECASE | re.MULTILINE

    for pat in _as_list(graders.get("must_match")):
        ok = re.search(pat, text, flags) is not None
        out.append(
            {"kind": "must_match", "pattern": pat, "passed": ok,
             "detail": "" if ok else "no match"}
        )

    for pat in _as_list(graders.get("must_not_match")):
        hit = re.search(pat, text, flags)
        out.append(
            {"kind": "must_not_match", "pattern": pat, "passed": hit is None,
             "detail": "" if hit is None else "matched %r" % hit.group(0)[:60]}
        )

    any_of = _as_list(graders.get("must_match_any"))
    if any_of:
        ok = any(re.search(p, text, flags) for p in any_of)
        out.append(
            {"kind": "must_match_any", "pattern": " | ".join(any_of), "passed": ok,
             "detail": "" if ok else "none of the alternatives matched"}
        )

    n = graders.get("min_chars")
    if n:
        ok = len(text.strip()) >= int(n)
        out.append(
            {"kind": "min_chars", "pattern": str(n), "passed": ok,
             "detail": "" if ok else "response is %d chars" % len(text.strip())}
        )

    for spec in _as_list(graders.get("must_match_count")):
        pat, minimum = spec["pattern"], int(spec.get("min", 1))
        found = len(re.findall(pat, text, flags))
        out.append(
            {"kind": "must_match_count", "pattern": "%s >= %d" % (pat, minimum),
             "passed": found >= minimum, "detail": "found %d" % found}
        )
    return out


# --------------------------------------------------------------------------
# eval families
# --------------------------------------------------------------------------


SKILL_ON_PREAMBLE = (
    "The following skill is available to you and applies to this task. "
    "Follow it.\n\n<skill>\n%s\n</skill>"
)


def run_usefulness(suite: Suite, runner, modes) -> list:
    rows = []
    for case in suite.cases:
        prompt = case.prompt
        for path, content in case.files.items():
            prompt += "\n\n%s:\n```\n%s\n```" % (path, content.rstrip())
        row = {"skill": suite.skill, "case": case.id, "note": case.note, "modes": {}}
        for mode in modes:
            system = SKILL_ON_PREAMBLE % suite.skill_md if mode == "on" else ""
            key = "%s/%s.%s" % (suite.skill, case.id, mode)
            text = runner.generate(prompt, system=system, key=key)
            checks = apply_graders(text, case.graders)
            row["modes"][mode] = {
                "passed": bool(checks) and all(c["passed"] for c in checks),
                "checks": checks,
                "chars": len(text),
                "available": bool(text),
            }
        rows.append(row)
    return rows


DISCOVERY_JUDGE = """You are the skill selector for a coding agent.
Below are the skills installed in this repository, each with its description.

{catalog}

A user sends this message:
<message>
{prompt}
</message>

Reply with the name of the single skill that should load for this message, or
the word NONE if no skill applies. Reply with the name only, nothing else."""


def run_discovery(suites: list, runner, target: Suite) -> dict:
    catalog = "\n".join(
        "- %s: %s" % (s.skill, s.description) for s in suites
    )
    results = {"should_trigger": [], "should_not_trigger": []}
    for i, prompt in enumerate(target.should_trigger):
        key = "%s/discovery.pos%d" % (target.skill, i)
        raw = runner.generate(
            DISCOVERY_JUDGE.format(catalog=catalog, prompt=prompt), key=key
        )
        picked = raw.strip().splitlines()[0].strip() if raw.strip() else ""
        results["should_trigger"].append(
            {"prompt": prompt, "picked": picked, "passed": picked == target.skill,
             "available": bool(raw)}
        )
    for i, prompt in enumerate(target.should_not_trigger):
        key = "%s/discovery.neg%d" % (target.skill, i)
        raw = runner.generate(
            DISCOVERY_JUDGE.format(catalog=catalog, prompt=prompt), key=key
        )
        picked = raw.strip().splitlines()[0].strip() if raw.strip() else ""
        results["should_not_trigger"].append(
            {"prompt": prompt, "picked": picked, "passed": picked != target.skill,
             "available": bool(raw)}
        )
    return results


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------


def summarise(report: dict) -> list:
    """Collapse the raw report into one row per skill."""
    rows = []
    for skill, data in sorted(report["skills"].items()):
        use = data["usefulness"]
        graded = [r for r in use if all(m.get("available") for m in r["modes"].values())]
        on = sum(1 for r in graded if r["modes"].get("on", {}).get("passed"))
        off = sum(1 for r in graded if r["modes"].get("off", {}).get("passed"))
        disc = data["discovery"]
        pos = disc.get("should_trigger", [])
        neg = disc.get("should_not_trigger", [])
        pos_graded = [p for p in pos if p.get("available")]
        neg_graded = [n for n in neg if n.get("available")]
        rows.append(
            {
                "skill": skill,
                "cases": len(use),
                "graded": len(graded),
                "on": on,
                "off": off,
                "discovery_hit": "%d/%d" % (sum(1 for p in pos_graded if p["passed"]), len(pos))
                if pos_graded
                else "-",
                "adversarial_clean": "%d/%d" % (sum(1 for n in neg_graded if n["passed"]), len(neg))
                if neg_graded
                else "-",
            }
        )
    return rows


def markdown_table(rows: list, runner_name: str, model: str, when: str) -> str:
    if not rows:
        return "_No eval results yet._"
    head = (
        "| Skill | Cases | Passed with skill | Passed without | Discovery hit | "
        "Adversarial clean |\n|---|---|---|---|---|---|\n"
    )
    body = ""
    for r in rows:
        if r["graded"] == 0:
            on = off = "not run"
        else:
            on = "%d/%d" % (r["on"], r["graded"])
            off = "%d/%d" % (r["off"], r["graded"])
        body += "| `%s` | %d | %s | %s | %s | %s |\n" % (
            r["skill"], r["cases"], on, off, r["discovery_hit"], r["adversarial_clean"]
        )
    footer = "\n_runner: %s · model: %s · %s_\n" % (runner_name, model, when)
    return head + body + footer


README_START = "<!-- EVAL-RESULTS:START -->"
README_END = "<!-- EVAL-RESULTS:END -->"


def write_readme_block(readme: Path, table: str) -> bool:
    text = readme.read_text(encoding="utf-8")
    if README_START not in text or README_END not in text:
        return False
    head, rest = text.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    readme.write_text(
        head + README_START + "\n" + table + README_END + tail, encoding="utf-8"
    )
    return True


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--skills-dir", default=str(REPO_ROOT / "skills"))
    ap.add_argument("--skill", action="append", default=[], help="limit to this skill (repeatable)")
    ap.add_argument("--runner", choices=["replay", "cli", "api"], default="replay")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--transcripts", default=str(REPO_ROOT / "evals" / "transcripts"))
    ap.add_argument("--record", action="store_true", help="save responses as transcripts")
    ap.add_argument("--family", choices=["all", "usefulness", "discovery"], default="all")
    ap.add_argument("--out", default=str(REPO_ROOT / "evals" / "out" / "results.json"))
    ap.add_argument("--markdown", default="", help="also write the summary table here")
    ap.add_argument("--update-readme", action="store_true")
    ap.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit 1 unless skill-on pass rate over graded cases is at least this (0-1)",
    )
    args = ap.parse_args()

    suites = load_suites(Path(args.skills_dir), args.skill)
    if not suites:
        print("no eval suites found", file=sys.stderr)
        return 2

    runner = build_runner(args, Path(args.transcripts))
    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    report = {"generated": when, "runner": runner.name, "model": args.model, "skills": {}}

    for suite in suites:
        print("== %s" % suite.skill)
        usefulness = (
            run_usefulness(suite, runner, ["on", "off"])
            if args.family in ("all", "usefulness")
            else []
        )
        discovery = (
            run_discovery(suites, runner, suite)
            if args.family in ("all", "discovery")
            else {}
        )
        report["skills"][suite.skill] = {"usefulness": usefulness, "discovery": discovery}
        for row in usefulness:
            on = row["modes"].get("on", {})
            off = row["modes"].get("off", {})
            if not on.get("available"):
                print("   %-28s no transcript (run with --runner cli --record)" % row["case"])
                continue
            print(
                "   %-28s on=%s off=%s"
                % (row["case"], "pass" if on.get("passed") else "FAIL",
                   "pass" if off.get("passed") else "fail")
            )
            for c in on.get("checks", []):
                if not c["passed"]:
                    print("        missed [%s] %s %s" % (c["kind"], c["pattern"], c["detail"]))

    rows = summarise(report)
    table = markdown_table(rows, runner.name, args.model, when)
    print("\n" + table)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("raw results: %s" % out)

    if args.markdown:
        Path(args.markdown).write_text(table, encoding="utf-8")
    if args.update_readme:
        if write_readme_block(REPO_ROOT / "README.md", table):
            print("README results block updated")
        else:
            print("README has no EVAL-RESULTS markers; left alone", file=sys.stderr)

    if isinstance(runner, ReplayRunner) and runner.missing:
        print(
            "\n%d case(s) had no recorded transcript; they are reported as "
            "'not run', not as passes." % len(runner.missing)
        )

    if args.fail_under is not None:
        graded = sum(r["graded"] for r in rows)
        passed = sum(r["on"] for r in rows)
        rate = (passed / graded) if graded else 0.0
        print("skill-on pass rate: %.2f over %d graded case(s)" % (rate, graded))
        if graded == 0 or rate < args.fail_under:
            print("below --fail-under %.2f" % args.fail_under, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
