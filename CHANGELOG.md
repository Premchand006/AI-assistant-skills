# Changelog

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
