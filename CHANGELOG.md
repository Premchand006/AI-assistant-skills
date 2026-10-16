# Changelog

## Unreleased

### Fixed

- A fresh clone failed `tools/test_scripts.py` (7/8): the unanchored `runs/`
  rule in `.gitignore` also ignored the OpenLane failed-run fixture under
  `evals/fixtures/openlane/runs/`. The fixture is now re-included and committed.
- A fresh `pip install -r requirements-dev.txt` failed the ONNX smoke test:
  `quant_pre_process` needs `sympy` for symbolic shape inference and
  onnxruntime does not declare it. Added to `requirements-dev.txt`;
  `quantize_onnx.py` now says how to install it instead of failing mid-run.
- `eval_runner.py` graded a failed `claude -p` call as model output: the
  `[runner error] ...` text was non-empty, so it counted as an available
  response. Every generation now has a status (`ok`, `missing`, `empty`,
  `runner_error`, `timeout`); only `ok` is graded, failures are never recorded
  as transcripts, timeouts and missing binaries are caught, and the runner
  exits 1 when any generation failed. A failed discovery call no longer counts
  as "correctly stayed quiet".
- `eval_runner.py --record` built transcript paths from case ids without
  checking them, so an id containing `../` could write outside
  `evals/transcripts/`. Skill names and case ids must now be slugs, duplicates
  are rejected, and every path is checked to resolve under its root.
- `lint_rtl.sh` interpolated filenames into a `yosys -p` string, so a filename
  containing `;` could inject Yosys commands. It now writes a quoted `.ys`
  script and refuses names containing `;`, `#`, `"` or control characters;
  `--top` must be a plain identifier.
- `lint_rtl.sh` and `run_static.sh`: an option missing its argument
  (`--top`, `--compile-db`) exits 2 with a message; directory scans are
  null-delimited, so filenames with newlines survive; paths beginning with `-`
  are passed as `./-...` so tools cannot read them as options.
- README claimed Python 3.8+; CI tests 3.10, 3.12 and 3.13. The documented
  minimum is now 3.10.

- CI: `actions/setup-python` failed with "No file matched to
  `[**/requirements.txt or **/pyproject.toml]`" because the dependency file
  here is `requirements-dev.txt`. Added `cache-dependency-path`.
- CI: `actions/checkout@v4` and `actions/setup-python@v5` run on the deprecated
  Node 20 runtime. Both moved to `@v7`, which runs on Node 24.
- CI: `shellcheck -S warning` failed on `run_static.sh` with SC2054, a false
  positive on a cppcheck argument that legitimately contains commas. The array
  element is now quoted. Both wrapper scripts are clean at `-S style`.
- `lint_rtl.sh` and `run_static.sh` hardcoded `python3`, so on a machine where
  the interpreter is `python` they reported "at least one check reported a
  problem" — turning a missing interpreter into what looked like a failed
  check. They now resolve `python3`, `python` or `py`, honour `PYTHON=...`, and
  exit 2 with an explanation when none is found.

### Added

- `tools/check_transcripts.py`: scans transcripts for credentials, private
  keys, e-mail addresses, home-directory paths and confidentiality markers.
  The recorder sends matching responses to `evals/out/quarantine/` instead of
  `evals/transcripts/`; CI scans the committed directory.
- `tools/test_eval_runner.py`: unit tests for the harness's failure semantics,
  path containment, suite validation, exit codes and the transcript scan.
- `--fail-on-missing` for `eval_runner.py`, and a `release evidence` CI job on
  `v*` tags that uses it, so a release cannot publish results without
  transcripts behind them. `make evidence` runs it locally.
- `results.json` records the commit and dirty state, Python and OS, per-skill
  suite hashes, and per-response prompt/response hashes, latency and token use.
- The API runner retries 429/5xx/connection errors up to five times (SDK
  backoff) and records failures instead of aborting the run.
- `SECURITY.md`, `.env.example`, and `.gitignore` entries for `.env`, keys and
  coverage output.

- `.gitattributes` pinning shell and source files to LF, so a clone on Windows
  cannot produce CRLF scripts that fail on a Linux runner.
- `.github/dependabot.yml` for monthly action and pip updates, so a runtime
  deprecation arrives as a pull request rather than as a failed build.
- `.editorconfig`, a pull request template, and two issue templates: one for a
  skill that gave bad guidance, one for a checker that reported the wrong
  thing.
- CI job step that runs both wrapper scripts on a machine with no EDA tools
  installed, checking they report what was skipped instead of failing.
- CI now also tests on Python 3.13.

### Changed

- CI actions are pinned to full commit SHAs (`actions/checkout` v7.0.1,
  `actions/setup-python` v7.0.0); Dependabot bumps them.

- Repository and plugin naming settled: marketplace `ai-assistant-skills`,
  plugin `silicon-skills`, owner `Premchand006`.

## 0.1.0 — unreleased

First cut. Seven skills, the harness that grades them, and the CI that keeps
them honest.

### Skills

- `rtl-verilog-lint` — synthesisable Verilog/SystemVerilog, with
  `check_synthesizable.py` (12 rules) and `lint_rtl.sh` wrapping Verilator,
  Verible and Yosys.
- `rtl-testbench-discipline` — self-checking testbenches, SVA, coverage,
  cocotb and UVM, with `check_testbench.py` for SystemVerilog and cocotb.
- `timing-closure-cdc` — STA reports and clock-domain crossings, with
  `cdc_scan.py` inferring domains and classifying each crossing.
- `openlane-sky130-flow` — OpenLane 2 RTL-to-GDSII, with `check_config.py` and
  `summarize_run.py`.
- `embedded-firmware-misra` — Cortex-M firmware, with `check_isr_safety.py` and
  `run_static.sh` wrapping cppcheck and clang-tidy.
- `onnx-quantize-tflm` — INT8 quantisation and TFLite Micro deployment, with
  `quantize_onnx.py` and `tflite_report.py`.
- `skill-eval-harness` — writing and evaluating skills, with `new_skill.py`.

### Harness

- `evals/eval_runner.py` — usefulness (skill-on vs skill-off), discovery and
  adversarial discovery, with replay, CLI and API runners. Cases with no
  transcript report as "not run", never as passes.
- `tools/validate_skills.py` — frontmatter, size budgets, house style,
  referenced files, eval-file structure.
- `tools/test_scripts.py` — every bundled checker against fixtures with planted
  defects, plus clean fixtures it must stay quiet on.
- `tools/smoke_imports.py` — compilation, dependency-error handling, and the
  ONNX quantisation path end to end.

### Known gaps

- No eval transcripts recorded yet, so the README results table reads "not run"
  for every skill.
- `tflite_report.py` is not covered by the test suite: it needs a real
  `.tflite` model and a TFLite interpreter. Only its dependency handling is
  checked.
- Every checker is a single-file heuristic. None preprocesses, elaborates or
  follows references across files.
