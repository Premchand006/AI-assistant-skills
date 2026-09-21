# How these skills are evaluated

This describes exactly what the numbers in the README mean, how they are
produced, and what they do not cover. If something here is unconvincing, the
transcripts are committed and the graders are readable — disagree in an issue.

## What is measured

Three families per skill, all defined in `skills/<name>/evals/eval.yaml` and
run by `evals/eval_runner.py`.

### Usefulness

The same prompt is sent twice: once with the skill's `SKILL.md` in the system
prompt, once without. Both responses are graded by the same deterministic
checks. The headline number is how many cases passed in each mode.

Putting the skill in the system prompt rather than relying on the harness to
select it is deliberate. It isolates the skill's *content* from the harness's
*selection*, which the discovery family measures separately. Conflating the two
produces a number that moves when either changes.

Cases are written from mistakes models actually make. A case where the
skill-off answer is already correct measures nothing and inflates the result,
so reviewers reject those.

### Discovery

The model is shown the frontmatter descriptions of every skill in the
repository and nothing else, plus a user message, and asked which skill should
load. A prompt passes if it selects the skill under test.

This is a model of skill selection, not the mechanism itself. The real
mechanism also weighs conversation history and other context. A skill that
passes here can still fail to trigger in a long conversation; a skill that
fails here will almost certainly never fire.

### Adversarial discovery

The same setup with prompts that share vocabulary with the skill but belong
elsewhere: a neighbouring skill's territory, a concept question with nothing to
act on, a prompt from a different field using the same words. A prompt passes
if the skill under test is *not* selected.

This is the false-positive rate of the description. It is where context bloat
comes from, and it is the family most skill collections omit entirely.

## Grading

Graders are deterministic regular expressions, applied case-insensitively and
multiline:

| Grader | Passes when |
|---|---|
| `must_match` | every pattern matches |
| `must_not_match` | no pattern matches |
| `must_match_any` | at least one alternative matches |
| `must_match_count` | a pattern appears at least `min` times |
| `min_chars` | the response is at least this long |

A case passes only if every grader on it passes.

Two rules keep the graders from measuring vocabulary instead of substance.
Graders list the set of acceptable approaches rather than one required word, so
that rewording the skill does not break them. And `must_not_match` patterns are
written from an actual skill-off response, not from imagination — an invented
pattern usually matches nothing in either mode and silently does nothing.

Graders are assertions written by the same people who wrote the skills. They
inherit those people's blind spots, which is a real limitation and not a
formality.

## Runners

| Runner | Source of responses | Needs |
|---|---|---|
| `replay` (default) | committed transcripts in `evals/transcripts/` | nothing |
| `cli` | `claude -p`, one call per case | the `claude` binary |
| `api` | Anthropic Messages API | `anthropic`, `ANTHROPIC_API_KEY` |

```bash
python3 evals/eval_runner.py --runner cli --record     # produce transcripts
python3 evals/eval_runner.py --runner replay           # re-grade them
python3 evals/eval_runner.py --skill rtl-verilog-lint --runner cli --record
```

CI runs `replay`. That verifies the published table still follows from the
recorded responses and the current graders; it makes no model call and tells
you nothing new about the current model. Re-record when the model changes.

A case with no recorded transcript is reported as **not run**, never as a pass.
The summary states how many fell into that category.

## Reading the numbers correctly

"4/5 with the skill, 1/5 without" means: across five cases *chosen because the
model tends to get them wrong*, the skill fixed three more than the baseline.

It does not mean the skill improves answers 80% of the time. The case selection
is adversarial by design, so the result is a floor on a deliberately hard
sample. Every skill eval published anywhere has this property; stating it is
the difference between a measurement and an advertisement.

Results are per model and per version. They do not transfer.

## What is not measured

- **Whether the produced code compiles or runs.** Graders check text. A case
  that verifies the model chose a gray-coded crossing does not verify that the
  gray-code conversion it wrote is correct.
- **Tasks nobody wrote a case for.** Coverage is 5 usefulness cases per skill.
- **Whether a skill degrades unrelated conversations** beyond what the
  adversarial prompts sample.
- **Interaction between skills.** Each skill is graded alone; installing all
  seven has effects this harness does not measure.
- **Long-conversation behaviour.** Every case is a single turn.

## Separate from the evals: what CI proves today

These are mechanical checks, they run on every push, and they are the claims
currently backed by evidence:

| Check | What it establishes |
|---|---|
| `tools/validate_skills.py --strict` | every skill meets the frontmatter, size and style rules |
| `tools/test_scripts.py` | every bundled checker finds the planted defects in the fixtures and stays quiet on the clean ones |
| `tools/smoke_imports.py` | every script compiles, dependency-missing paths explain themselves, the ONNX quantisation runs end to end |
| `evals/eval_runner.py --runner replay` | the results table follows from the committed transcripts |

None of these establish that a skill improves model output. That is what the
usefulness family is for, and until transcripts are recorded the README says
"not run" rather than implying otherwise.
