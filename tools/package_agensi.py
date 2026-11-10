#!/usr/bin/env python3
"""Build Agensi.io upload zips from skills/.

Output (dist/agensi/, git-ignored):
  <skill>.zip               one per skill: <skill>/SKILL.md, scripts/, references/, LICENSE
  silicon-skills-pack.zip   every skill in one pack, with a README.md naming it

What it does to the copies (the repo's own SKILL.md files are never touched):
  - drops evals/ (they need the repo-level harness and fixtures) and caches
  - adds summary / tags / keywords / docs_url to the frontmatter, which the
    Agensi upload form reads to pre-fill the listing

Usage:
  python tools/package_agensi.py            # build all
  python tools/package_agensi.py rtl-verilog-lint m5-onboard
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
OUT = ROOT / "dist" / "agensi"
REPO_URL = "https://github.com/Premchand006/AI-assistant-skills"

EXCLUDE_DIRS = {"evals", "__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

# Listing metadata. summary is the one-line card text on Agensi.
META: dict[str, dict] = {
    "rtl-verilog-lint": {
        "summary": "Catch Verilog/SystemVerilog that simulates but won't synthesise: latches, blocking assigns, resets, multiple drivers.",
        "tags": ["verilog", "systemverilog", "rtl", "fpga", "asic", "lint"],
        "keywords": ["latch inference", "synthesis", "yosys", "verilator", "verible"],
    },
    "rtl-testbench-discipline": {
        "summary": "Self-checking testbenches that can actually fail: scoreboards, watchdogs, SVA, coverage, cocotb, UVM.",
        "tags": ["verification", "testbench", "systemverilog", "cocotb", "uvm"],
        "keywords": ["sva", "assertions", "functional coverage", "scoreboard", "constrained random"],
    },
    "timing-closure-cdc": {
        "summary": "Fix setup/hold violations and clock-domain crossings: STA reports, SDC, synchronisers, async FIFOs.",
        "tags": ["timing", "sta", "cdc", "sdc", "asic", "fpga"],
        "keywords": ["setup hold", "clock domain crossing", "synchronizer", "gray code", "opensta"],
    },
    "openlane-sky130-flow": {
        "summary": "Drive OpenLane 2 RTL-to-GDSII on Sky130/GF180: config.json, floorplan, DRC/LVS/antenna, failed-run triage.",
        "tags": ["openlane", "sky130", "open-silicon", "asic", "tapeout", "eda"],
        "keywords": ["openroad", "gdsii", "magic drc", "netgen lvs", "gf180mcu"],
    },
    "embedded-firmware-misra": {
        "summary": "Cortex-M/RTOS firmware that survives the field: ISR safety, volatile vs atomicity, registers, stack, MISRA C.",
        "tags": ["embedded", "firmware", "c", "misra", "cortex-m", "rtos"],
        "keywords": ["interrupt", "isr", "stm32", "freertos", "zephyr", "cppcheck"],
    },
    "m5-onboard": {
        "summary": "Provision and flash M5Stack/ESP32 boards: serial ports, download mode, esptool offsets, MicroPython via mpremote.",
        "tags": ["esp32", "m5stack", "micropython", "embedded", "iot"],
        "keywords": ["esptool", "mpremote", "flashing", "bootloader", "cardputer"],
    },
    "cpp-coding-standards": {
        "summary": "Modern C++17/20/23 per the ISO Core Guidelines: RAII, ownership, Rule of Zero/Five, bounds and type safety.",
        "tags": ["cpp", "c++", "code-review", "coding-standards"],
        "keywords": ["core guidelines", "raii", "smart pointers", "undefined behavior", "concepts"],
    },
    "cpp-testing": {
        "summary": "GoogleTest, GoogleMock and CTest done right: layout, fixtures, fakes vs mocks, sanitizer-gated tests.",
        "tags": ["cpp", "c++", "testing", "googletest", "cmake"],
        "keywords": ["gtest", "gmock", "ctest", "asan", "ubsan", "tsan"],
    },
    "latency-critical-systems": {
        "summary": "Tame p99 latency: zero-alloc hot paths, false sharing, cache-line alignment, lock-free queues, profiling.",
        "tags": ["performance", "latency", "cpp", "systems", "real-time"],
        "keywords": ["p99", "jitter", "false sharing", "lock-free", "hot path"],
    },
    "onnx-quantize-tflm": {
        "summary": "Get a model onto a microcontroller: INT8 quantisation with real calibration, TFLite Micro arena sizing, CMSIS-NN.",
        "tags": ["edge-ai", "tinyml", "onnx", "tflite", "quantization", "embedded"],
        "keywords": ["int8", "tflite micro", "cmsis-nn", "tensor arena", "calibration"],
    },
    "skill-eval-harness": {
        "summary": "Write agent skills that trigger correctly and measurably help: frontmatter, descriptions, three-family evals.",
        "tags": ["agent-skills", "evals", "claude-code", "prompt-engineering"],
        "keywords": ["skill.md", "eval suite", "discovery", "adversarial", "skill authoring"],
    },
}


def _q(s: str) -> str:
    # JSON strings are valid YAML double-quoted scalars, so ": " etc. are safe.
    return json.dumps(s, ensure_ascii=False)


def _yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(_q(i) for i in items) + "]"


def enrich_frontmatter(text: str, name: str) -> str:
    """Insert listing fields before the closing '---' of the frontmatter."""
    if not text.startswith("---"):
        raise SystemExit(f"{name}: SKILL.md has no frontmatter")
    end = text.index("\n---", 3)
    head, rest = text[:end], text[end:]
    meta = META.get(name)
    if meta is None:
        raise SystemExit(f"{name}: add an entry to META in {Path(__file__).name}")
    extra = []
    for key in ("summary", "tags", "keywords"):
        if f"\n{key}:" in head:
            continue  # already present in the source; leave it
        val = meta[key]
        extra.append(f"{key}: {_yaml_list(val) if isinstance(val, list) else _q(val)}")
    if "\ndocs_url:" not in head:
        extra.append(f"docs_url: {REPO_URL}/tree/main/skills/{name}")
    return head + ("\n" + "\n".join(extra) if extra else "") + rest


def skill_files(skill_dir: Path):
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(skill_dir)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIXES:
            continue
        yield p, rel


def add_skill(zf: zipfile.ZipFile, skill_dir: Path, prefix: str) -> int:
    name = skill_dir.name
    n = 0
    for p, rel in skill_files(skill_dir):
        arc = f"{prefix}{name}/{rel.as_posix()}"
        if rel.as_posix() == "SKILL.md":
            data = enrich_frontmatter(p.read_text(encoding="utf-8"), name)
            zf.writestr(arc, data.encode("utf-8"))
        else:
            zf.write(p, arc)
        n += 1
    zf.write(ROOT / "LICENSE", f"{prefix}{name}/LICENSE")
    return n + 1


PACK_README = f"""# Silicon Skills Pack

Skills for open-silicon, embedded firmware and edge AI: synthesisable RTL,
self-checking testbenches, timing closure and CDC, OpenLane/Sky130, Cortex-M
firmware and MISRA, ESP32/M5Stack provisioning, modern C++ and testing,
latency-critical systems, model quantisation for microcontrollers, and skill
evaluation.

Each skill ends with an honest-limits section. The bundled checkers are
regex heuristics; Verilator, Yosys, cppcheck and real CDC/synthesis tools remain
the authorities.

Source, eval suites and committed transcripts: {REPO_URL}
License: MIT
"""


def main(argv: list[str]) -> int:
    names = argv or sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names:
        skill_dir = SKILLS / name
        if not (skill_dir / "SKILL.md").is_file():
            print(f"skip {name}: no SKILL.md", file=sys.stderr)
            continue
        target = OUT / f"{name}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            count = add_skill(zf, skill_dir, "")
        print(f"{target.relative_to(ROOT)}  ({count} files, {target.stat().st_size // 1024} KB)")

    if not argv:
        pack = OUT / "silicon-skills-pack.zip"
        with zipfile.ZipFile(pack, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("silicon-skills-pack/README.md", PACK_README)
            for name in names:
                add_skill(zf, SKILLS / name, "silicon-skills-pack/skills/")
        print(f"{pack.relative_to(ROOT)}  ({pack.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
