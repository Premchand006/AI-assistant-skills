# Designing evals that tell you something

Loaded on demand.

## The three families, and what each one can fail

**Usefulness.** The same prompt with and without the skill, graded the same
way. It answers: does this skill change the answer, in the right direction?
Failure mode it catches: a skill that restates what the model already does.

**Discovery.** With every skill's description visible and nothing else, does a
prompt that should select this skill select it? Failure mode it catches: a
perfectly good skill with a description that never fires, which is the most
common way a skill delivers nothing.

**Adversarial discovery.** Prompts that share vocabulary with the skill but
belong elsewhere. Failure mode it catches: a greedy description that loads a
5000-token skill into every conversation about a loosely adjacent topic. This
is where context bloat comes from, and it is the family most repos skip.

A skill that passes usefulness and fails discovery is not a working skill. A
skill that passes both and fails adversarial is a tax on every other
conversation.

## Writing a usefulness case

The case has to be one where the skill-off answer is plausibly wrong. If both
modes pass, the case measures nothing and inflates your numbers.

The reliable source of cases is a real mistake: something a model actually got
wrong, or a bug you have seen in production. Invented cases tend to test what
you already wrote down, which is circular.

```yaml
- id: shared-counter
  note: >
    The skill-off answer is very often "yes, volatile is enough", which is the
    single most expensive misconception in embedded C.
  prompt: |
    I have `volatile uint32_t packet_count;` incremented in my UART ISR and
    also decremented in my main loop. Is volatile enough?
  graders:
    must_match:
      - "no|not (enough|sufficient)"
    must_match_any:
      - "atomic|read-modify-write"
```

The `note` field carries why the case exists. Six months later it is the only
thing that tells you whether a failure means the skill regressed or the case
was always weak.

## Graders

| Grader | Passes when |
|---|---|
| `must_match` | every regex matches (case-insensitive, multiline) |
| `must_not_match` | no regex matches |
| `must_match_any` | at least one alternative matches |
| `must_match_count` | a pattern appears at least `min` times |
| `min_chars` | the response is at least this long |

A case passes only if every grader passes. That is strict on purpose: a
partially correct answer to a hardware question is usually a wrong one.

Two rules that keep graders honest:

**Grade the substance, not the vocabulary.** `must_match: "gray"` tests whether
the model said a word. `must_match_any: ["gray", "handshake", "FIFO"]` plus
`must_not_match: "just add a two-flop synchroniser"` tests whether it picked a
correct approach and avoided the wrong one. The second survives a rewrite of
the skill; the first breaks.

**Write the negative grader from the actual bad answer.** Run the prompt with
the skill off, read what comes back, and make the pattern match that. A
`must_not_match` invented from imagination usually matches nothing in either
mode and silently does nothing.

## Discovery prompts

Write them the way a user types, not the way a documentation page reads.

- One that names the domain: "write a testbench for this FIFO"
- One that names a tool or an error instead of the domain: "Vivado says
  inferred latch"
- One where the skill applies but its vocabulary is absent: "my design
  simulates fine but the chip counts wrong"

For adversarial prompts, the useful ones are near misses: the neighbouring
skill's territory, a concept question with nothing to act on, and a prompt that
shares vocabulary with a different field. "Write pytest tests for my Python
pipeline" belongs in the adversarial set of a testbench skill precisely because
it shares the word "test".

## Running them

```bash
# Record once against a real model, with the skill on and off.
python3 ../../evals/eval_runner.py --skill my-skill --runner cli --record

# Re-check the recorded results any time, with no API key. This is what CI runs.
python3 ../../evals/eval_runner.py --skill my-skill --runner replay
```

The replay runner is what makes published numbers checkable: the transcripts
are committed, so anyone can re-grade them, disagree with a grader, and see it.
A results table that nobody can reproduce is a marketing claim.

The `on` mode puts the skill's text in the system prompt and the `off` mode
does not. That isolates the skill's content from the harness's skill-selection
behaviour, which the discovery family tests separately.

## Reading the numbers

A result of "4/5 with, 1/5 without" means: of five cases where the skill-off
answer was expected to be wrong, the skill fixed three and missed one. It does
not mean the skill improves answers 80% of the time, because the cases were
selected to be ones the model gets wrong. Selection bias runs through every
skill eval published anywhere, and stating it is the difference between a
measurement and an advertisement.

What the numbers do not cover:

- Whether the skill helps on tasks nobody wrote a case for.
- Whether it helps a different model. Results are per model and per version.
- Whether the graders test the right thing. A grader is an assertion written
  by the same person who wrote the skill.
- Whether the skill hurts unrelated conversations, beyond what the adversarial
  prompts sample.

## When a skill fails its own evals

Fix it or remove it. A skill that does not beat its own skill-off baseline is
context spent for nothing, and shipping it because it took a week to write is
how repositories end up making their users' output worse. Removing a skill is
a normal outcome of measuring, not an admission of failure.
