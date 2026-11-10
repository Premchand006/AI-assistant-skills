# AI-assistant-skills

**Agent skills for Verilog/SystemVerilog RTL, OpenLane/Sky130, embedded C firmware, modern C++, ESP32 and TinyML. Each one ships with the evals that show whether it helps.**

[![checks](https://github.com/Premchand006/AI-assistant-skills/actions/workflows/test.yml/badge.svg)](https://github.com/Premchand006/AI-assistant-skills/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Skills: 11](https://img.shields.io/badge/skills-11-informational.svg)
![Format: SKILL.md](https://img.shields.io/badge/format-SKILL.md-lightgrey.svg)

AI coding assistants write Verilog that simulates and will not synthesise,
firmware that works on the bench and fails in the field, and quantised models
with accuracy nobody measured. These eleven skills target those specific
mistakes. They bring runnable checkers and patterns, and each one ends by
saying what it cannot see.

They are plain `SKILL.md` folders: a Claude Code plugin, and usable by any
agent that reads the Agent Skills format.

Every skill is graded three ways: does it change the answer, does it trigger
when it should, and does it stay quiet when it should not. The transcripts are
committed so you can re-grade them yourself.

```bash
/plugin marketplace add Premchand006/AI-assistant-skills
/plugin install silicon-skills@ai-assistant-skills
```

**Contents:** [Skills](#what-is-in-it) ·
[Which skill do I need?](#which-skill-do-i-need) ·
[Install](#install) · [Try the checkers](#try-it-without-installing-anything) ·
[Eval results](#eval-results) · [Grading](#how-the-grading-works) ·
[Verified today](#what-is-verified-today) · [Scope](#honest-scope) ·
[FAQ](#faq) · [Contributing](#contributing)

## What is in it

| Skill | For | Ships with |
|---|---|---|
| [`rtl-verilog-lint`](skills/rtl-verilog-lint/) | Synthesisable Verilog/SystemVerilog: latches, blocking assignments, reset style, multiple drivers | `check_synthesizable.py`, `lint_rtl.sh` |
| [`rtl-testbench-discipline`](skills/rtl-testbench-discipline/) | Testbenches that decide pass/fail: scoreboards, watchdogs, SVA, coverage, cocotb, UVM | `check_testbench.py` |
| [`timing-closure-cdc`](skills/timing-closure-cdc/) | STA failures and clock-domain crossings: setup vs hold, synchroniser choice, SDC | `cdc_scan.py` |
| [`openlane-sky130-flow`](skills/openlane-sky130-flow/) | RTL-to-GDSII on OpenLane 2 / Sky130: config, floorplan, congestion, sign-off | `check_config.py`, `summarize_run.py` |
| [`embedded-firmware-misra`](skills/embedded-firmware-misra/) | Cortex-M firmware: ISR safety, `volatile` vs atomicity, registers, stack, MISRA | `check_isr_safety.py`, `run_static.sh` |
| [`m5-onboard`](skills/m5-onboard/) | ESP32 and M5Stack boards: USB detection, bootloader download mode, firmware flashing, MicroPython | guidance for `esptool.py`, `mpremote` |
| [`cpp-coding-standards`](skills/cpp-coding-standards/) | Modern C++ (C++17/20/23): ISO Core Guidelines, RAII, Rule of Zero/Five, memory safety | `core-guidelines.md` reference |
| [`cpp-testing`](skills/cpp-testing/) | GoogleTest, GoogleMock, and CTest: test layout, fakes, fixtures, AddressSanitizer gating | `gtest-patterns.md` reference |
| [`latency-critical-systems`](skills/latency-critical-systems/) | Low-latency systems: zero-alloc hot paths, p99 profiling, cache-line alignment, lock-free queues | `latency-patterns.md` reference |
| [`onnx-quantize-tflm`](skills/onnx-quantize-tflm/) | Models onto MCUs: INT8 calibration, TFLite Micro arena, CMSIS-NN | `quantize_onnx.py`, `tflite_report.py` |
| [`skill-eval-harness`](skills/skill-eval-harness/) | Writing and evaluating skills, including these ones | `new_skill.py` |

## Which skill do I need?

Start from the symptom. With the plugin installed you do not pick: the
assistant loads the matching skill from its description. These are the
situations each description is written to catch.

| You are seeing | Skill |
|---|---|
| RTL passes simulation but synthesis infers a latch, or post-synthesis behaviour differs | `rtl-verilog-lint` |
| Yosys, Verilator or Verible reports an elaboration error or multiple drivers | `rtl-verilog-lint` |
| A testbench exits 0 after a failure, hangs forever, or never checks its outputs | `rtl-testbench-discipline` |
| You need SVA properties, a covergroup, a cocotb test or a UVM agent | `rtl-testbench-discipline` |
| Negative setup or hold slack, or a signal crossing between two clocks | `timing-closure-cdc` |
| Writing or fixing an SDC file; intermittent hardware failures simulation cannot reproduce | `timing-closure-cdc` |
| An OpenLane 2 run fails on congestion, antenna, DRC, LVS or timing | `openlane-sky130-flow` |
| Writing a `config.json` for a Sky130 or GF180MCU tapeout | `openlane-sky130-flow` |
| A Cortex-M or STM32 device works on the bench and fails intermittently in the field | `embedded-firmware-misra` |
| Reviewing an ISR, a ring buffer, a register header, or FreeRTOS/Zephyr task code | `embedded-firmware-misra` |
| An ESP32 or M5Stack board will not enter download mode, or `esptool` flashing fails | `m5-onboard` |
| Reviewing C++ for ownership, RAII, `const`-correctness or undefined behaviour | `cpp-coding-standards` |
| GoogleTest/CTest setup, flaky tests, or ASan/UBSan/TSan in a C++ test suite | `cpp-testing` |
| p99 latency spikes, jitter, false sharing, or heap allocation on a hot path | `latency-critical-systems` |
| Accuracy drops after INT8 quantisation, or a TFLite Micro arena fails to allocate | `onnx-quantize-tflm` |
| Writing a new skill, or a skill that does not trigger or does not help | `skill-eval-harness` |

## Install

**Claude Code (plugin marketplace).** Installs all eleven skills as one plugin:

```bash
/plugin marketplace add Premchand006/AI-assistant-skills
/plugin install silicon-skills@ai-assistant-skills
```

**Any agent that reads `SKILL.md`.** Each skill is a self-contained folder.
Copy the folders you want into your agent's skills directory, for example
`~/.claude/skills/` for Claude Code:

```bash
git clone https://github.com/Premchand006/AI-assistant-skills
cp -r AI-assistant-skills/skills/rtl-verilog-lint ~/.claude/skills/
```

Installers that pull skills from a GitHub repository, such as
`npx skills add Premchand006/AI-assistant-skills`, also work, because the
layout is the standard `skills/<name>/SKILL.md`.

The `evals/` folder inside each skill is only used by this repository's
harness. It is safe to leave out of an install.

## Try it without installing anything

The checkers run standalone against the fixtures in this repo:

```bash
git clone https://github.com/Premchand006/AI-assistant-skills
cd AI-assistant-skills

# RTL that simulates but will not synthesise
python3 skills/rtl-verilog-lint/scripts/check_synthesizable.py \
        evals/fixtures/rtl/bad_fifo.sv --fail-on never

# A clock-domain crossing that RTL simulation and STA both miss
python3 skills/timing-closure-cdc/scripts/cdc_scan.py \
        evals/fixtures/rtl/cdc_mixed.sv --fail-on never

# Firmware that works on the bench and fails in the field
python3 skills/embedded-firmware-misra/scripts/check_isr_safety.py \
        evals/fixtures/firmware/uart_driver.c --fail-on never
```

```text
cdc_mixed.sv:36: error: [multibit-2ff] multi-bit signal 'data_fast' crosses
    clk_fast -> clk_slow through a two-flop synchroniser
    hint: the bits settle independently, so the destination can sample a value
          that never existed; use gray coding, a handshake, or an async FIFO
```

The checkers need Python 3.10+ (the versions CI tests) and nothing else: no
EDA tools, no ML libraries. On Windows use `python` in place of `python3`. The
two wrapper scripts (`lint_rtl.sh`, `run_static.sh`) find the interpreter
themselves and accept `PYTHON=...` to override it.

## Eval results

<!-- EVAL-RESULTS:START -->
| Skill | Cases | Passed with skill | Passed without | Discovery hit | Adversarial clean |
|---|---|---|---|---|---|
| `cpp-coding-standards` | 2 | not run | not run | - | - |
| `cpp-testing` | 2 | not run | not run | - | - |
| `embedded-firmware-misra` | 5 | not run | not run | - | - |
| `latency-critical-systems` | 2 | not run | not run | - | - |
| `m5-onboard` | 2 | not run | not run | - | - |
| `onnx-quantize-tflm` | 5 | not run | not run | - | - |
| `openlane-sky130-flow` | 5 | not run | not run | - | - |
| `rtl-testbench-discipline` | 5 | not run | not run | - | - |
| `rtl-verilog-lint` | 5 | not run | not run | - | - |
| `skill-eval-harness` | 5 | not run | not run | - | - |
| `timing-closure-cdc` | 5 | not run | not run | - | - |

_runner: replay · model: claude-sonnet-5 · 2026-11-10 07:21 UTC_
<!-- EVAL-RESULTS:END -->

43 usefulness cases, 59 discovery prompts and 59 adversarial prompts are
written and committed. **"not run" means no transcript exists for that case,
and it is never counted as a pass.** The table above is generated by the
harness. It says "not run" everywhere because no model run has been recorded
yet, and it will report numbers only once transcripts are in the repository.

To produce the numbers yourself:

```bash
pip install -r requirements-dev.txt
python3 evals/eval_runner.py --runner cli --record   # calls `claude -p` per case
python3 evals/eval_runner.py --runner replay         # re-grade, no API key
```

A live run sends each prompt, its fixture files and (in skill-on mode) the full
`SKILL.md` to the model provider. Use only material you are allowed to share.
Responses are scanned before they are written to `evals/transcripts/`; anything
that looks like a credential or personal data goes to `evals/out/quarantine/`
instead. See [SECURITY.md](SECURITY.md).

`--runner replay` re-grades the committed transcripts, so anyone can check the
table, disagree with a grader, and show it. A results table nobody can
reproduce is a marketing claim; this one is meant to be attacked.

## How the grading works

Three families per skill, described in full in
[docs/eval-methodology.md](docs/eval-methodology.md):

- **Usefulness:** the same prompt with the skill in the system prompt and
  without it, graded by the same deterministic checks. Cases are written from
  mistakes models actually make, so a case where both modes pass is a case that
  measures nothing.
- **Discovery:** given only the frontmatter descriptions of all eleven skills,
  does a prompt that should select this one select it? A skill that helps but
  never triggers delivers nothing.
- **Adversarial discovery:** prompts that share vocabulary with the skill and
  belong elsewhere. This is the false-positive rate of the description, and it
  is where context bloat comes from.

Because the usefulness cases are chosen to be ones a model tends to get wrong,
the numbers are a floor on a deliberately hard sample, not a success rate.

## What is verified today

Run these yourself; they are what CI runs on every push.

```bash
python3 tools/validate_skills.py --strict   # 11/11 skills pass
python3 tools/test_scripts.py               # 8/8 script checks pass
python3 tools/test_eval_runner.py           # eval harness failure semantics
python3 tools/check_transcripts.py          # no secrets in committed transcripts
python3 tools/smoke_imports.py              # 17 scripts compile; ONNX path runs
python3 tools/check_docs_sync.py            # README, llms.txt, manifests match the repo
```

`make check` runs all of these. These numbers hold on a fresh clone with
`pip install -r requirements-dev.txt`, which is what CI starts from.

| Claim | Evidence |
|---|---|
| Every skill meets the frontmatter and size budgets | `tools/validate_skills.py --strict`, in CI |
| Every checker finds the planted defects and stays quiet on clean fixtures | `tools/test_scripts.py`, 8 cases, in CI |
| The ONNX quantisation path runs end to end and reports accuracy | `tools/smoke_imports.py`, against `evals/fixtures/edge/` |
| A runner error, timeout or missing transcript is never graded as a model answer | `tools/test_eval_runner.py`, in CI |
| The counts and skill lists in this README are current | `tools/check_docs_sync.py`, in CI |
| The skills measurably improve model output | **not yet measured**; see the table above |
| `tflite_report.py` produces a correct report | **not covered**; needs a real `.tflite` and an interpreter, so only its dependency handling is tested |

## Honest scope

- **Domain.** Digital design, silicon implementation on the open flow, Cortex-M
  class firmware, ESP32 provisioning, modern C++ and its tests, latency
  engineering, and model deployment to MCUs. Not analog, not RF, not Linux
  drivers, not server-side inference.
- **The checkers are heuristics.** They parse text with regular expressions
  after stripping comments. They do not elaborate designs, expand macros or
  preprocess C, so each one misses defects inside macros and across module or
  translation-unit boundaries. Every `SKILL.md` ends with a section spelling out
  what its scripts cannot see. Verilator, Yosys, cppcheck, a real CDC tool and
  synthesis remain the authorities.
- **A clean run means the installed checks found nothing.** The wrapper scripts
  print which tools were missing, because skipped is not passed.
- **The newest skills are thinner.** `cpp-coding-standards`, `cpp-testing`,
  `latency-critical-systems` and `m5-onboard` ship reference material rather
  than checkers, and have two usefulness cases each where the others have five.
- **Eleven skills, deliberately.** Breadth is where skill quality goes to die
  and where context bloat starts. A skill that fails its own evals gets fixed or
  removed rather than shipped.

## FAQ

**Does this only work with Claude?**
The format is the open `SKILL.md` layout: YAML frontmatter with `name` and
`description`, a Markdown body, and optional `scripts/` and `references/`.
The Claude Code plugin manifest is one way to install it. The evals call
`claude -p` by default, but the graders only read text.

**Do the checkers replace Verilator, Yosys or cppcheck?**
No. They catch the specific defect patterns the skills teach, with no
dependencies, so an assistant can run them anywhere. The wrapper scripts call
the real tools when they are installed and say which ones were skipped.

**Why does every eval result say "not run"?**
No model run has been recorded and committed yet. The harness refuses to report
a number without a transcript behind it. See [Eval results](#eval-results) to
record one yourself.

**Can I use one skill without the others?**
Yes. Each skill folder is self-contained. Descriptions name their neighbours
("not for testbench structure, which belongs to `rtl-testbench-discipline`") so
that installing several does not make them fight over the same prompt.

**How do I write a skill that meets this bar?**
Start with `skill-eval-harness`, then
[docs/authoring-skills.md](docs/authoring-skills.md).

## Contributing

New skills are welcome in these domains, with an eval suite. A pull request has
to pass `tools/validate_skills.py --strict`, include usefulness cases the
baseline plausibly fails, include adversarial discovery prompts, and carry an
honest-limits section. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/authoring-skills.md](docs/authoring-skills.md).

```bash
python3 skills/skill-eval-harness/scripts/new_skill.py my-skill-name
```

## License

MIT. Every skill here is written for this repository; no `SKILL.md` text is
copied from another project.
