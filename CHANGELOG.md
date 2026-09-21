# Changelog

## Unreleased

### Fixed

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
