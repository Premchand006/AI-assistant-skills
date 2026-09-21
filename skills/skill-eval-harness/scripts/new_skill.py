#!/usr/bin/env python3
"""Scaffold a new skill with its eval suite already in place.

Creates skills/<name>/ with a SKILL.md skeleton, a references/ and scripts/
directory, and an evals/eval.yaml containing the three eval families with
placeholder cases. The placeholders are deliberately unfilled: a skill whose
eval file still says TODO fails validation, which is the point.

Usage:
    python new_skill.py my-skill-name
    python new_skill.py my-skill-name --skills-dir ../../skills
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILL_TEMPLATE = '''---
name: {name}
description: TODO one or two sentences on what this does, then a "Use when ..." clause naming the concrete triggers - file types, tool names, error messages, task phrasings. Aim for 300-800 characters; the hard cap is 1024. Name what this skill is not for and which skill covers that instead.
license: MIT
version: 0.1.0
---

# {title}

TODO Open with the failure this skill exists to prevent. One or two sentences.
A model reading this needs to know why the guidance matters before it needs the
guidance.

## TODO the main workflow

TODO The steps, in order. Put the commands the model should run early, since
running the bundled script is usually more reliable than reasoning from the
prose.

```bash
python3 scripts/TODO.py target/ --fail-on error
```

## TODO the rules that matter

TODO The guidance itself. Explain why each rule exists rather than issuing it
as an imperative - a model that knows the reason handles the case you did not
anticipate. Keep the body under 500 lines and roughly 5000 tokens; move depth
into references/ and say when to read it.

Detail lives in [references/TODO.md](references/TODO.md). Say here what
question sends the reader there.

## Honest limits

TODO What this skill and its scripts do not cover, what the scripts cannot see,
and what a clean result does not prove. This section is not a disclaimer. It is
what stops a model reporting more confidence than the evidence supports.
'''

EVAL_TEMPLATE = '''skill: {name}

# Discovery: with only the frontmatter descriptions of every skill in the repo
# visible, does this prompt select this skill?
discovery:
  should_trigger:
    - "TODO a phrasing a user would actually type"
    - "TODO a phrasing that names a tool or error rather than the topic"
    - "TODO a phrasing where the skill applies but the topic word is absent"
  # Adversarial: superficially related, should select something else or nothing.
  should_not_trigger:
    - "TODO a neighbouring task owned by a different skill"
    - "TODO a concept question with nothing to act on"
    - "TODO a prompt sharing vocabulary but not the domain"

usefulness:
  - id: TODO-case-id
    note: >
      TODO What failure this case is designed to catch, and what the typical
      skill-off answer gets wrong. A case where both modes pass is measuring
      nothing.
    prompt: |
      TODO the user's message
    # Optional file context pasted into the prompt.
    # files:
    #   path/to/file.ext: |
    #     TODO contents
    graders:
      must_match:
        - "TODO regex the good answer contains"
      must_not_match:
        - "TODO regex the bad answer contains"
      must_match_any:
        - "TODO alternative"
        - "TODO alternative"
      # min_chars: 300
      # must_match_count:
      #   - pattern: "TODO"
      #     min: 2
'''

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("name")
    ap.add_argument("--skills-dir", type=Path, default=None)
    args = ap.parse_args()

    if not NAME_RE.match(args.name):
        print("name must be lowercase-kebab-case, e.g. rtl-verilog-lint", file=sys.stderr)
        return 2

    skills_dir = args.skills_dir
    if skills_dir is None:
        here = Path(__file__).resolve()
        # scripts/ -> skill/ -> skills/
        skills_dir = here.parent.parent.parent

    target = skills_dir / args.name
    if target.exists():
        print("%s already exists" % target, file=sys.stderr)
        return 1

    (target / "references").mkdir(parents=True)
    (target / "scripts").mkdir()
    (target / "evals").mkdir()

    title = args.name.replace("-", " ").title()
    (target / "SKILL.md").write_text(
        SKILL_TEMPLATE.format(name=args.name, title=title), encoding="utf-8"
    )
    (target / "evals" / "eval.yaml").write_text(
        EVAL_TEMPLATE.format(name=args.name), encoding="utf-8"
    )

    print("created %s" % target)
    print("\nnext:")
    print("  1. write the description first, then the discovery evals from it")
    print("  2. write the usefulness cases before the body, so the body has a target")
    print("  3. python tools/validate_skills.py")
    print("  4. python evals/eval_runner.py --skill %s --runner cli --record" % args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
