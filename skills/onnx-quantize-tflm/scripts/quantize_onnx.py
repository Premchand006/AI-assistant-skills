#!/usr/bin/env python3
"""Post-training static INT8 quantisation for ONNX models, with a measurement.

Quantisation is a four-times size reduction in exchange for accuracy you have
to measure. This does the quantisation the way edge targets want it (QDQ
format, per-channel weights, real calibration data) and then reports what it
cost, because a quantised model shipped without that number is a guess.

Usage:
    python quantize_onnx.py model.onnx -o model.int8.onnx --calib data/calib
    python quantize_onnx.py model.onnx -o out.onnx --calib data/ --compare
    python quantize_onnx.py model.onnx -o out.onnx --calib data/ \\
        --activation-type uint16 --weight-type int8        # for tricky models

Calibration data: a directory of .npy files, each one input for a single
inference, or a single .npz whose keys are input names. Use data from the real
distribution; random noise produces ranges that have nothing to do with the
ones the model will see.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def require(module: str, install: str):
    try:
        return __import__(module)
    except ImportError:
        print("this script needs %s: python -m pip install %s" % (module, install),
              file=sys.stderr)
        raise SystemExit(2)


np = require("numpy", "numpy")
require("onnx", "onnx")
require("onnxruntime", "onnxruntime")

import onnxruntime  # noqa: E402
from onnxruntime.quantization import (  # noqa: E402
    CalibrationDataReader,
    CalibrationMethod,
    QuantFormat,
    QuantType,
    quantize_static,
)
from onnxruntime.quantization.shape_inference import quant_pre_process  # noqa: E402

QUANT_TYPES = {
    "int8": QuantType.QInt8,
    "uint8": QuantType.QUInt8,
    "int16": QuantType.QInt16,
    "uint16": QuantType.QUInt16,
}
CALIB_METHODS = {
    "minmax": CalibrationMethod.MinMax,
    "entropy": CalibrationMethod.Entropy,
    "percentile": CalibrationMethod.Percentile,
}


class DirectoryDataReader(CalibrationDataReader):
    """Feeds calibration samples from .npy/.npz files on disk."""

    def __init__(self, model_path: str, calib_dir: Path, limit: int = 0):
        session = onnxruntime.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        self.inputs = session.get_inputs()
        self.samples = self._load(calib_dir, limit)
        if not self.samples:
            raise SystemExit(
                "no calibration samples found in %s (expected .npy or .npz files)" % calib_dir
            )
        self.iter = None

    def _load(self, calib_dir: Path, limit: int):
        names = [i.name for i in self.inputs]
        samples = []
        files = sorted(list(calib_dir.glob("*.npy")) + list(calib_dir.glob("*.npz")))
        for f in files:
            if f.suffix == ".npz":
                data = np.load(f)
                samples.append({k: data[k] for k in data.files if k in names})
            else:
                arr = np.load(f)
                if len(names) != 1:
                    raise SystemExit(
                        "model has %d inputs (%s); use .npz files with one array per input"
                        % (len(names), ", ".join(names))
                    )
                samples.append({names[0]: self._fit(arr, self.inputs[0])})
            if limit and len(samples) >= limit:
                break
        return samples

    @staticmethod
    def _fit(arr, meta):
        """Add a batch axis when the sample is missing one, and cast to float32."""
        arr = np.asarray(arr)
        expected = len(meta.shape) if meta.shape else arr.ndim
        if arr.ndim == expected - 1:
            arr = arr[None, ...]
        dtype = np.float32 if "float" in (meta.type or "") else arr.dtype
        return arr.astype(dtype, copy=False)

    def get_next(self):
        if self.iter is None:
            self.iter = iter(self.samples)
        return next(self.iter, None)

    def rewind(self):
        self.iter = None


def compare(fp32_path: str, int8_path: str, reader: DirectoryDataReader) -> dict:
    """Run both models on the calibration samples and report the difference."""
    s32 = onnxruntime.InferenceSession(fp32_path, providers=["CPUExecutionProvider"])
    s8 = onnxruntime.InferenceSession(int8_path, providers=["CPUExecutionProvider"])
    max_abs, cos_sims, agree, total = 0.0, [], 0, 0

    for sample in reader.samples:
        a = s32.run(None, sample)[0].astype(np.float64).ravel()
        b = s8.run(None, sample)[0].astype(np.float64).ravel()
        if a.shape != b.shape:
            continue
        max_abs = max(max_abs, float(np.max(np.abs(a - b))))
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom > 0:
            cos_sims.append(float(np.dot(a, b) / denom))
        if a.size > 1:
            agree += int(np.argmax(a) == np.argmax(b))
        total += 1

    return {
        "samples": total,
        "max_abs_diff": max_abs,
        "mean_cosine_similarity": float(np.mean(cos_sims)) if cos_sims else float("nan"),
        "argmax_agreement": (agree / total) if total else float("nan"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("model", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--calib", type=Path, required=True, help="directory of .npy/.npz samples")
    ap.add_argument("--limit", type=int, default=0, help="use at most N calibration samples")
    ap.add_argument("--activation-type", choices=sorted(QUANT_TYPES), default="int8")
    ap.add_argument("--weight-type", choices=sorted(QUANT_TYPES), default="int8")
    ap.add_argument("--calib-method", choices=sorted(CALIB_METHODS), default="minmax")
    ap.add_argument("--per-channel", dest="per_channel", action="store_true", default=True)
    ap.add_argument("--no-per-channel", dest="per_channel", action="store_false")
    ap.add_argument("--compare", action="store_true", help="measure fp32 vs int8 outputs")
    ap.add_argument("--keep-preprocessed", action="store_true")
    args = ap.parse_args()

    if not args.model.is_file():
        print("no such model: %s" % args.model, file=sys.stderr)
        return 2
    if not args.calib.is_dir():
        print("no such calibration directory: %s" % args.calib, file=sys.stderr)
        return 2

    # Shape inference and folding first. Skipping this is the most common cause
    # of "quantisation ran but the model got slower".
    preproc = args.output.with_suffix(".preproc.onnx")
    print("preprocessing (shape inference + folding) -> %s" % preproc)
    quant_pre_process(str(args.model), str(preproc), skip_symbolic_shape=False)

    reader = DirectoryDataReader(str(preproc), args.calib, args.limit)
    print("calibrating on %d sample(s) from %s" % (len(reader.samples), args.calib))

    quantize_static(
        str(preproc),
        str(args.output),
        reader,
        quant_format=QuantFormat.QDQ,       # QDQ is what edge runtimes expect
        activation_type=QUANT_TYPES[args.activation_type],
        weight_type=QUANT_TYPES[args.weight_type],
        per_channel=args.per_channel,
        calibrate_method=CALIB_METHODS[args.calib_method],
    )

    fp32_size = args.model.stat().st_size
    int8_size = args.output.stat().st_size
    print("\nwrote %s" % args.output)
    print("  fp32: %8.1f KiB" % (fp32_size / 1024))
    print("  int8: %8.1f KiB  (%.2fx smaller)" % (int8_size / 1024, fp32_size / max(int8_size, 1)))

    if args.compare:
        reader.rewind()
        stats = compare(str(args.model), str(args.output), reader)
        print("\naccuracy against fp32, on the calibration set:")
        print("  samples               %d" % stats["samples"])
        print("  max abs difference    %.6f" % stats["max_abs_diff"])
        print("  mean cosine similarity %.6f" % stats["mean_cosine_similarity"])
        print("  argmax agreement      %.1f%%" % (100 * stats["argmax_agreement"]))
        print(
            "\nThese numbers come from the calibration set, which the quantiser has "
            "already seen. Measure the real metric on a held-out set before shipping."
        )

    if not args.keep_preprocessed:
        preproc.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
