# Security policy

## Reporting a vulnerability

Report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/Premchand006/AI-assistant-skills/security/advisories/new)
for this repository. Do not open a public issue for something exploitable.
Expect an acknowledgement within a week.

In scope: the bundled scripts (`skills/*/scripts/`, `tools/`, `evals/`), the
CI workflow, and anything in a `SKILL.md` that would lead an agent to run
something unsafe. Examples: a crafted filename or eval case that makes a script
write outside its directory or run unintended commands; a transcript workflow
that publishes a secret.

## Supported versions

Only the latest commit on `main` and the latest tagged release receive fixes.

## What these tools are not

The checkers are regex heuristics. They do not elaborate RTL, expand macros or
preprocess C, and they are not a security or safety boundary. A clean run means
the installed checks found nothing. Verilator, Yosys, cppcheck, a real CDC tool,
a MISRA checker and synthesis remain the authorities; do not substitute these
scripts for them in a safety or certification argument.

Run the checkers on code you trust or inside a container. They read whole files
into memory and recurse into directories without size or count limits, so a
hostile tree can make them slow or memory-hungry.

## Live eval runs and transcripts

`evals/eval_runner.py --runner cli|api` sends each prompt, the case's fixture
files and, in skill-on mode, the full `SKILL.md` to the model provider. Keep
fixtures synthetic. The API key is read from `ANTHROPIC_API_KEY` in the
environment and is never written to disk by these scripts; keep it out of the
repository (`.env` is git-ignored) and avoid debug-level SDK logging on shared
machines, since it can include request content.

Recorded responses are scanned by `tools/check_transcripts.py` before they are
written to `evals/transcripts/`, and CI scans that directory on every push. The
scan is pattern-based; review a transcript before committing it.
