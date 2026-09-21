#!/usr/bin/env python3
"""Inspect a .tflite model for microcontroller deployment.

Answers the four questions you need before writing any C++:
  1. Is it fully integer quantised, or does it still have float in the graph?
  2. Which operators does it use, and what does the op resolver look like?
  3. Roughly how big a tensor arena will it need?
  4. What are the input and output quantisation parameters, so the C++ side
     scales its data the same way the training pipeline did?

Needs a TFLite interpreter:
    python -m pip install ai-edge-litert     # or: tensorflow

Usage:
    python tflite_report.py model.tflite
    python tflite_report.py model.tflite --resolver     # emit the C++ lines
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_interpreter_class():
    try:
        from ai_edge_litert.interpreter import Interpreter  # type: ignore

        return Interpreter
    except ImportError:
        pass
    try:
        from tensorflow.lite.python.interpreter import Interpreter  # type: ignore

        return Interpreter
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter  # type: ignore

        return Interpreter
    except ImportError:
        print(
            "no TFLite interpreter available. Install one:\n"
            "    python -m pip install ai-edge-litert\n"
            "  or\n"
            "    python -m pip install tensorflow",
            file=sys.stderr,
        )
        raise SystemExit(2)


# TFLite builtin op name -> MicroMutableOpResolver method.
RESOLVER_METHODS = {
    "ADD": "AddAdd", "AVERAGE_POOL_2D": "AddAveragePool2D", "CONCATENATION":
    "AddConcatenation", "CONV_2D": "AddConv2D", "DEPTHWISE_CONV_2D":
    "AddDepthwiseConv2D", "DEQUANTIZE": "AddDequantize", "FULLY_CONNECTED":
    "AddFullyConnected", "LOGISTIC": "AddLogistic", "MAX_POOL_2D":
    "AddMaxPool2D", "MEAN": "AddMean", "MUL": "AddMul", "PAD": "AddPad",
    "QUANTIZE": "AddQuantize", "RELU": "AddRelu", "RELU6": "AddRelu6",
    "RESHAPE": "AddReshape", "RESIZE_NEAREST_NEIGHBOR":
    "AddResizeNearestNeighbor", "SOFTMAX": "AddSoftmax", "STRIDED_SLICE":
    "AddStridedSlice", "SUB": "AddSub", "TANH": "AddTanh", "TRANSPOSE":
    "AddTranspose", "SHAPE": "AddShape", "SQUEEZE": "AddSqueeze", "SPLIT":
    "AddSplit", "PACK": "AddPack", "UNPACK": "AddUnpack", "SVDF": "AddSvdf",
    "LEAKY_RELU": "AddLeakyRelu", "MAXIMUM": "AddMaximum", "MINIMUM":
    "AddMinimum", "ARG_MAX": "AddArgMax", "EXPAND_DIMS": "AddExpandDims",
    "SLICE": "AddSlice", "SUM": "AddSum", "BATCH_MATMUL": "AddBatchMatMul",
}
# Ops with no MicroMutableOpResolver method in the standard build.
NOT_IN_TFLM = {
    "FLEX", "CUSTOM", "WHILE", "IF", "CALL_ONCE", "RFFT2D", "COMPLEX_ABS",
}


def dtype_name(t) -> str:
    return getattr(t, "__name__", str(t))


def report(model_path: Path, emit_resolver: bool) -> int:
    Interpreter = load_interpreter_class()
    interp = Interpreter(model_path=str(model_path))
    interp.allocate_tensors()

    inputs = interp.get_input_details()
    outputs = interp.get_output_details()
    tensors = interp.get_tensor_details()
    try:
        ops = interp._get_ops_details()
    except AttributeError:
        ops = []

    size_kb = model_path.stat().st_size / 1024
    print("model: %s  (%.1f KiB flash)" % (model_path.name, size_kb))

    # --- 1. quantisation --------------------------------------------------
    print("\n-- quantisation")
    int_types = ("int8", "uint8", "int16", "int32", "int64")
    problems = []
    for kind, details in (("input", inputs), ("output", outputs)):
        for d in details:
            dt = dtype_name(d["dtype"])
            scale, zero = d["quantization"]
            print("  %-7s %-22s %-8s scale=%-12.8g zero_point=%d"
                  % (kind, d["name"][:22], dt, scale, zero))
            if dt not in int_types:
                problems.append(
                    "%s '%s' is %s, not an integer type" % (kind, d["name"], dt)
                )

    float_tensors = [
        t for t in tensors
        if dtype_name(t["dtype"]) == "float32" and t["quantization"][0] == 0
    ]
    if problems:
        print("\n  NOT fully integer quantised:")
        for p in problems:
            print("    - " + p)
        print(
            "    TFLite Micro can run float, but it costs flash for the float kernels\n"
            "    and is far slower without an FPU. For a fully integer model, set:\n"
            "      converter.inference_input_type  = tf.int8\n"
            "      converter.inference_output_type = tf.int8\n"
            "      converter.target_spec.supported_ops = "
            "[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]"
        )
    else:
        print("\n  fully integer quantised at the boundary")
    if float_tensors:
        print("  note: %d unquantised float tensor(s) remain inside the graph"
              % len(float_tensors))

    # --- 2. operators -----------------------------------------------------
    op_names = []
    for op in ops:
        name = op.get("op_name", "")
        if name and name not in op_names:
            op_names.append(name)
    print("\n-- operators (%d distinct, %d nodes)" % (len(op_names), len(ops)))
    unsupported = []
    for name in op_names:
        method = RESOLVER_METHODS.get(name)
        if name in NOT_IN_TFLM or method is None:
            unsupported.append(name)
            print("  %-26s no standard TFLM resolver method" % name)
        else:
            print("  %-26s %s()" % (name, method))
    if unsupported:
        print(
            "\n  %d operator(s) have no standard TFLite Micro kernel. Either replace\n"
            "  them in the model, or register a custom kernel with AddCustom()."
            % len(unsupported)
        )

    # --- 3. arena ---------------------------------------------------------
    total_bytes = 0
    per_op_peak = 0
    tensor_bytes = {}
    for t in tensors:
        n = 1
        for d in t["shape"]:
            n *= int(d)
        itemsize = getattr(t["dtype"], "itemsize", 1)
        b = n * itemsize
        tensor_bytes[t["index"]] = b
        total_bytes += b
    for op in ops:
        live = sum(
            tensor_bytes.get(i, 0)
            for i in list(op.get("inputs", [])) + list(op.get("outputs", []))
        )
        per_op_peak = max(per_op_peak, live)

    print("\n-- tensor arena")
    print("  floor (largest single op's tensors)  %8.1f KiB" % (per_op_peak / 1024))
    print("  ceiling (every tensor live at once)  %8.1f KiB" % (total_bytes / 1024))
    print(
        "  Start at the ceiling, then shrink it. TFLM reuses buffers, so the real\n"
        "  number is usually near the floor. Get the exact value from the device:\n"
        "      interpreter.arena_used_bytes()\n"
        "  These two numbers bracket it; neither is the answer."
    )

    # --- 4. C++ ----------------------------------------------------------
    if emit_resolver:
        usable = [n for n in op_names if n in RESOLVER_METHODS]
        print("\n-- C++ op resolver")
        print("  // %d operator(s); the template argument is the count" % len(usable))
        print("  static tflite::MicroMutableOpResolver<%d> resolver;" % max(len(usable), 1))
        for name in usable:
            print("  resolver.%s();" % RESOLVER_METHODS[name])
        if unsupported:
            print("  // no standard kernel for: %s" % ", ".join(unsupported))
        print("\n  constexpr int kTensorArenaSize = %d;  // tune with arena_used_bytes()"
              % (((total_bytes // 1024) + 1) * 1024))
        print("  alignas(16) static uint8_t tensor_arena[kTensorArenaSize];")
        if inputs:
            scale, zero = inputs[0]["quantization"]
            if scale:
                print("\n  // input quantisation: q = round(x / %.8g) + %d" % (scale, zero))
                print("  // the C++ side has to apply the same scaling the training")
                print("  // pipeline did, or the model sees a different distribution")

    return 1 if problems or unsupported else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("model", type=Path)
    ap.add_argument("--resolver", action="store_true", help="emit the C++ setup lines")
    args = ap.parse_args()

    if not args.model.is_file():
        print("no such file: %s" % args.model, file=sys.stderr)
        return 2
    return report(args.model, args.resolver)


if __name__ == "__main__":
    raise SystemExit(main())
