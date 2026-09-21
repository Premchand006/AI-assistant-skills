# Contributing

The bar here is evidence, not volume. A pull request adding one skill with
evals that show it helps is worth more than ten skills that read well.

## Scope

In scope: digital design and verification, silicon implementation on the open
flow, embedded firmware for MCU-class parts, and model deployment to edge
targets. Also meta-skills about building and evaluating skills.

Out of scope: general software engineering, web development, document
generation, "awesome list" style link collections, and anything whose value
depends on the model not already being good at it. If Claude already does the
task well, a skill about it costs context and returns nothing.

If you are unsure, open an issue describing the mistake you have seen a model
make. That mistake is the real proposal.

## Getting set up

```bash
git clone https://github.com/your-github-username/claude-essentials
cd claude-essentials
python3 -m pip install -r requirements-dev.txt
python3 tools/validate_skills.py --strict
python3 tools/test_scripts.py
```

## Adding a skill

```bash
python3 skills/skill-eval-harness/scripts/new_skill.py my-skill-name
```

That scaffolds `SKILL.md`, `references/`, `scripts/` and `evals/eval.yaml` with
the three eval families in place.

Write it in this order. The order is the point: a body written first documents
what you know, a body written against failing cases fixes what the model gets
wrong.

1. **The description.** It is the only text loaded before selection, so it
   decides whether the skill ever runs. Say what it does, when to use it with
   concrete triggers, and what it is not for with the skill that covers that
   instead.
2. **The discovery evals**, written from the description. Three prompts that
   should select it, at least three that should not.
3. **The usefulness cases**, from real mistakes. Run each prompt with the skill
   off first and read what comes back — that response is where the
   `must_not_match` patterns come from.
4. **The scripts.** Anything deterministic belongs in a script; its source
   never enters the context window.
5. **`SKILL.md`**, aimed at the cases, under 500 lines and ~5000 tokens.
6. **`references/`** for the depth, named from `SKILL.md` with a sentence
   saying what sends the reader there.
7. **The honest-limits section.** Every skill has one.

## What a pull request has to clear

- `python3 tools/validate_skills.py --strict` passes: frontmatter present and
  parsing, name matching the directory, description within 1024 characters and
  containing a "use when" clause, body within the size budgets, no all-caps
  imperatives outside code spans, every referenced file present, `eval.yaml`
  present with all three families.
- `python3 tools/test_scripts.py` passes, with a case added for any new script:
  a fixture with planted defects, the rules it must report, and a clean fixture
  it must stay quiet on.
- `python3 tools/smoke_imports.py` passes; a script whose dependency is missing
  prints how to install it rather than raising a traceback.
- At least three usefulness cases where the skill-off answer is plausibly
  wrong. A case both modes pass measures nothing, and reviewers will ask you to
  replace it.
- An honest-limits section naming what the skill's scripts cannot see.
- New shell scripts pass `shellcheck -S warning`.

Recorded transcripts are welcome but not required for a first pull request;
maintainers can record them. If you do record them, say which model and version
produced them.

## House style

**Explain the reason, do not issue the order.** A model that knows why
non-blocking assignments belong in clocked blocks handles the case you did not
anticipate. All-caps imperatives are rejected by the validator because they
usually mark the place where a reason went missing.

**Write for a competent practitioner who has not done this particular thing
before.** Not a tutorial, not a reference manual: the decisions, the traps, and
where to look for more.

**Be specific about uncertainty.** "This usually means X" and "this always
means X" are different claims, and the difference is what makes the skill worth
trusting.

**Prefer a script to a paragraph** wherever the work is deterministic.

## Licensing and attribution

Contributions are MIT. Do not copy `SKILL.md` text, reference material or
scripts from other repositories, including other skill collections. Techniques
and standards are shared knowledge; someone else's wording is theirs.

If a reference draws on a specific external source — a standard, a tool's
documentation, a paper — cite it in the reference file where a reader would
want to follow it up.

## Removing a skill

A skill that fails its own evals gets fixed or removed. Removal is a normal
outcome of measuring, and a pull request that deletes a skill with the numbers
to justify it is as welcome as one that adds a skill.
