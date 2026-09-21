---
name: skill-eval-harness
description: Write, evaluate and maintain agent skills with measured evidence rather than assertion. Covers SKILL.md structure and frontmatter, writing a description that triggers reliably without firing on neighbouring topics, progressive disclosure through references and scripts, and building eval suites across three families - usefulness with skill on versus off, discovery, and adversarial discovery. Use when creating a new skill, reviewing or debugging one that does not trigger or does not help, deciding whether a skill earns its context cost, writing an eval suite or grader, or interpreting skill eval results. Also use when asked whether a skill is any good.
license: MIT
version: 0.1.0
---

# Skills, measured

Independent testing of published skill collections keeps finding the same
thing: most skills do not help, and a meaningful share make output worse. The
ones that help are written by someone who knows the domain and were iterated
against evaluation. So the question for any skill is not whether it reads well,
it is whether it beats the same model without it — and that is answerable.

## Order of work

1. Write the `description`. It is the only text loaded before selection, so it
   decides whether the skill ever runs.
2. Write the discovery evals from the description, before the body. This
   catches the description that reads well and selects nothing.
3. Write usefulness cases from real mistakes — something a model actually got
   wrong. A case where the skill-off answer is already correct measures
   nothing.
4. Write the scripts. Deterministic work belongs in a script, whose source
   never enters context.
5. Write `SKILL.md` aimed at the cases, and move depth to `references/`.
6. Run the evals. If the skill does not beat its own baseline, fix it or drop
   it.

```bash
python3 scripts/new_skill.py my-skill-name      # scaffold with evals in place
python3 ../../tools/validate_skills.py          # frontmatter, budgets, style
python3 ../../evals/eval_runner.py --skill my-skill-name --runner cli --record
python3 ../../evals/eval_runner.py --runner replay   # re-grade, no API key
```

## The three eval families

**Usefulness** runs the same prompt with the skill in the system prompt and
without it, graded identically. It answers whether the skill changes the answer
in the right direction.

**Discovery** shows the model every skill's description and nothing else, and
asks which one applies. A skill that helps but never triggers delivers nothing,
and this is the most common failure.

**Adversarial discovery** uses prompts that share vocabulary with the skill but
belong elsewhere. It measures the false-positive rate of the description, which
is where context bloat comes from. Most published skills have no equivalent
check.

Graders are deterministic regex checks (`must_match`, `must_not_match`,
`must_match_any`, `must_match_count`, `min_chars`) and a case passes only if
every grader passes. Grade the substance rather than the vocabulary: matching
one required word tests whether the model said it, while a set of acceptable
approaches plus a pattern matching the known bad answer tests whether it chose
correctly. Write the negative pattern from an actual skill-off response, not
from imagination — an invented one usually matches nothing and silently does
nothing.

Grader semantics, case design, and how to write discovery prompts the way users
actually type are in [references/eval-design.md](references/eval-design.md).

## Budgets and voice

`SKILL.md` body stays under 500 lines and roughly 5000 tokens; `description`
under 1024 characters, and under 1536 combined with `when_to_use`. Past those,
performance degrades measurably and the listing truncates.

Explain the reason rather than issuing an imperative. A model that knows why a
rule exists handles the case the author did not anticipate; a model given
`ALWAYS do X` follows it into situations where it does not apply. All-caps
imperatives usually mark the place where a reason went missing.

Structure, description writing, the YAML colon trap, and how skills differ from
MCP servers and subagents are in
[references/skill-anatomy.md](references/skill-anatomy.md).

## Reading results honestly

A result like "4/5 with the skill, 1/5 without" means that across five cases
chosen because the model tends to get them wrong, the skill fixed three more
than the baseline. It does not mean the skill improves answers 80% of the time.
Cases are selected adversarially, so the numbers are a floor on a biased
sample, not a success rate — and saying so is what separates a measurement from
an advertisement.

When reporting on a skill, state the model and version, how many cases ran, how
they were chosen, and what the graders actually check. Results do not transfer
between models.

## Honest limits

This harness grades text with regular expressions. It does not execute the code
a model produces, so a case that checks for a correct approach cannot tell you
the code compiles. It does not measure whether a skill helps on tasks nobody
wrote a case for, and it cannot tell whether the graders themselves test the
right thing — a grader is an assertion written by the same person who wrote the
skill, and it inherits their blind spots.

Discovery evals approximate skill selection with a judge prompt containing the
descriptions. That is a model of the real selection mechanism, not the
mechanism itself; the real one also weighs conversation history and other
context. A skill that passes discovery here can still fail to trigger in a long
conversation.

The replay runner re-grades recorded transcripts, so it verifies grading
reproducibly but tells you nothing new about the current model. Re-record when
the model changes, and say which model the published numbers came from.
