# Recorded transcripts

Model responses recorded by `evals/eval_runner.py --record`, committed so the
published results table can be re-graded by anyone with no API key and no model
call:

```bash
python3 evals/eval_runner.py --runner replay
```

## Layout

```
evals/transcripts/
└── <skill-name>/
    ├── <case-id>.on.md        # response with the skill in the system prompt
    ├── <case-id>.off.md       # response without it
    ├── discovery.pos0.md      # which skill the selector picked
    └── discovery.neg0.md
```

Each file is the raw response text, nothing else. The graders in
`skills/<name>/evals/eval.yaml` are applied to it as-is, so a transcript can be
re-graded after a grader changes without re-running the model.

## Recording

```bash
python3 evals/eval_runner.py --runner cli --record                    # all skills
python3 evals/eval_runner.py --skill rtl-verilog-lint --runner cli --record
python3 evals/eval_runner.py --runner api --record --model claude-sonnet-5
```

Only successful responses are recorded. A runner error or timeout is reported
in `evals/out/results.json` and never written here, so it cannot be replayed as
if the model had said it. A response that matches the secret and personal-data
scan in `tools/check_transcripts.py` is written to `evals/out/quarantine/`
instead; inspect it, and do not copy it here unless the match is a false
positive (mark that line with `transcript-scan: allow`). CI runs the same scan
over this directory.

When you commit transcripts, say in the pull request which model and version
produced them. Results do not transfer between models, and a table whose
provenance is unrecorded is not evidence.

## Why these are committed

A results table nobody can check is a claim, not a measurement. With the
transcripts in the repository, anyone can read what the model actually said,
decide the grader is too lenient or too strict, and open an issue with the
evidence in hand.

This directory is empty apart from this file until the first recording run. A
case with no transcript is reported as **not run**, never as a pass.
