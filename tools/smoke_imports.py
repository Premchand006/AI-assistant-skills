#!/usr/bin/env python3
"""Compile every bundled script, and run the ones whose dependencies are here.

Two jobs:
  1. Every script in skills/*/scripts/ compiles, and every script whose
     dependencies are missing says so clearly instead of raising a traceback.
  2. The ONNX quantisation path runs end to end when onnxruntime is installed,
     against the fixture model in evals/fixtures/edge/.

Scripts whose dependencies are absent are reported as skipped. Skipped is not
passed, and the summary says which is which.
"""
from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def compile_all() -> list:
    problems = []
    scripts = sorted(REPO.glob("skills/*/scripts/*.py")) + sorted(REPO.glob("tools/*.py")) + \
        sorted(REPO.glob("evals/*.py"))
    for s in scripts:
        try:
            py_compile.compile(str(s), doraise=True, cfile=str(
                Path(tempfile.gettempdir()) / (s.stem + ".pyc")))
        except py_compile.PyCompileError as exc:
            problems.append("%s: %s" % (s.relative_to(REPO), exc))
    print("compiled %d script(s): %s" % (len(scripts), "clean" if not problems else "FAILED"))
    for p in problems:
        print("  " + p)
    return problems


def check_graceful_dependency_error() -> list:
    """A script whose dependency is missing must explain, not traceback."""
    problems = []
    target = REPO / "skills/onnx-quantize-tflm/scripts/tflite_report.py"
    proc = subprocess.run(
        [PY, str(target), str(REPO / "evals/fixtures/edge/tiny_cnn.onnx")],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    combined = proc.stdout + proc.stderr
    if "Traceback" in combined:
        problems.append("tflite_report.py raised a traceback instead of a message")
    elif "pip install" not in combined and proc.returncode == 2:
        problems.append("tflite_report.py did not say how to install its dependency")
    if proc.returncode == 2 and "interpreter" in combined.lower():
        print("tflite_report.py: no TFLite interpreter installed, dependency message OK (SKIP)")
    else:
        print("tflite_report.py: interpreter present, ran with exit %d" % proc.returncode)
    return problems


def check_onnx_quantise() -> list:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        print("quantize_onnx.py: onnxruntime not installed (SKIP)")
        return []

    model = REPO / "evals/fixtures/edge/tiny_cnn.onnx"
    calib = REPO / "evals/fixtures/edge/calib"
    if not model.is_file() or not calib.is_dir():
        print("quantize_onnx.py: fixture model missing (SKIP)")
        return []

    out_dir = Path(tempfile.mkdtemp(prefix="quant-smoke-"))
    out = out_dir / "tiny.int8.onnx"
    try:
        proc = subprocess.run(
            [PY, str(REPO / "skills/onnx-quantize-tflm/scripts/quantize_onnx.py"),
             str(model), "-o", str(out), "--calib", str(calib), "--compare"],
            cwd=REPO, capture_output=True, text=True, timeout=600,
        )
        problems = []
        if proc.returncode != 0:
            problems.append("quantize_onnx.py exited %d: %s"
                            % (proc.returncode, proc.stderr.strip()[:400]))
        elif not out.is_file():
            problems.append("quantize_onnx.py reported success but wrote no model")
        else:
            for expected in ("argmax agreement", "cosine similarity", "smaller"):
                if expected not in proc.stdout:
                    problems.append("output is missing %r" % expected)
            print("quantize_onnx.py: quantised the fixture model and reported accuracy (PASS)")
        return problems
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def main() -> int:
    problems = []
    problems += compile_all()
    problems += check_graceful_dependency_error()
    problems += check_onnx_quantise()

    print()
    if problems:
        print("%d problem(s):" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
