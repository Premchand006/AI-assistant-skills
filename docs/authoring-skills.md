# Authoring rules and where they come from

The rules `tools/validate_skills.py` enforces, and the reasoning behind each.
The model-facing version of this material is in
[`skills/skill-eval-harness/references/skill-anatomy.md`](../skills/skill-eval-harness/references/skill-anatomy.md);
this page is for contributors and explains the enforcement.

## Layout

```
skills/<name>/
├── SKILL.md            # loaded into context when the skill triggers
├── references/         # loaded only when SKILL.md sends the model there
├── scripts/            # run via bash; source never enters context
└── evals/eval.yaml     # the three eval families
```

Progressive disclosure is the design. `SKILL.md` costs context every time the
skill loads, so it carries the decisions: what to do, in what order, why.
Depth goes to `references/`, named from `SKILL.md` with a sentence saying which
question sends the reader there. Deterministic work goes to `scripts/`, whose
contents the model never has to read.

## Enforced budgets

| Rule | Limit | Enforced by | Why |
|---|---|---|---|
| `SKILL.md` body | 500 lines / ~5000 tokens | validator, error | past this, agent performance degrades measurably |
| `description` | 1024 characters | validator, error | the hard cap in the open skill spec |
| `description` + `when_to_use` | 1536 characters | validator, error | Claude Code truncates the listing past this |
| `name` | lowercase-kebab-case, matches directory, ≤64 chars | validator, error | selection and paths both key off it |

The token estimate is `characters / 4`, rounded up. It is deliberately
conservative: it over-counts slightly, so a skill that passes locally does not
fail elsewhere.

## Enforced content rules

**A `description` must contain a "use when" clause.** The description is the
only text present before selection. One that says what a skill does but not
when to reach for it competes with every other skill on vibes.

**No all-caps imperatives** (`MUST`, `ALWAYS`, `NEVER`, `CRITICAL`,
`IMPORTANT`, `DO NOT`) outside inline code spans. Anthropic's skill-creator
flags these as a signal to reframe, and the reason is practical: a model told
`NEVER use blocking assignments in always_ff` follows the rule into cases where
it does not apply and has nothing to fall back on. A model told "`=` in a
clocked block creates a simulation race whose outcome depends on statement
order" can reason about the exception.

Inline code spans are exempt so a skill can quote the thing it is arguing
against.

**Every referenced file exists.** The validator collects markdown links and
bare `references/…`, `scripts/…` and `assets/…` paths from the body and checks
each one. A `SKILL.md` pointing at a file that was renamed sends the model to
read nothing.

**Every bundled file is referenced.** A warning, not an error: a script nobody
mentions will not be run.

**`evals/eval.yaml` exists** and contains `discovery.should_trigger`,
`discovery.should_not_trigger` and at least one `usefulness` case with `id`,
`prompt` and `graders`. A skill without adversarial prompts is a skill whose
false-positive rate nobody measured.

## Frontmatter

```yaml
---
name: rtl-verilog-lint          # lowercase-kebab, matches the directory
description: >                  # what, when, and what it is not for
  Write and review synthesisable Verilog... Use when writing, reviewing or
  debugging .v/.sv files... Not for testbench structure, which belongs to
  rtl-testbench-discipline.
license: MIT                    # warned if missing
version: 0.1.0                  # warned if missing
---
```

One YAML trap worth knowing before it costs you a debugging session: an
unquoted scalar containing `: ` breaks the parse. Writing `crossing structure:
two-flop synchroniser` inside an unquoted description makes YAML read it as a
nested mapping and the whole file fails. Either quote the string or rephrase
without the colon. The validator reports this with the parser's message and
column, which is usually enough to find it.

## Running the checks

```bash
python3 tools/validate_skills.py            # errors fail, warnings print
python3 tools/validate_skills.py --strict   # warnings fail too; this is CI
python3 tools/validate_skills.py --quiet    # only failures
```

Exit codes: 0 all pass, 1 at least one failure, 2 nothing to check.

## Writing scripts that belong in a skill

- **Single file, standard library where possible.** A script with a heavy
  dependency does not run on the machine where it is needed.
- **A missing dependency prints how to install it** and exits 2. It never
  raises a traceback. `tools/smoke_imports.py` checks this.
- **Structured output on request.** `--json` makes a script usable by the model
  as data rather than prose to re-read.
- **Meaningful exit codes**, so the script drops into a pre-commit hook or CI
  unchanged. The convention here is `--fail-on error|warn|info|never`.
- **Severities that mean something.** `error` is "this is wrong"; `warn` is
  "this is legal and usually a bug"; `info` is "worth a look". Reporting
  everything as an error trains the reader to ignore all of it.
- **A closing line about what the run did not check.** Every checker here ends
  by naming the real tools that remain the authority.
- **A fixture and a case in `tools/test_scripts.py`.** A checker with no test
  is a checker that can silently stop finding anything.

## Extending the validator

New rules go in `check_skill()` in `tools/validate_skills.py`, appending to
`res.errors` or `res.warnings`. Add the rule to the table above in the same
pull request, with the reason — a rule whose justification is not written down
gets removed by the next person who trips over it.
