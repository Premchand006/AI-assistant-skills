---
name: onnx-quantize-tflm
description: Take a trained neural network to a microcontroller or edge target. Covers post-training INT8 quantisation of ONNX models with real calibration data, TFLite full-integer conversion, choosing calibration sets, diagnosing accuracy loss, flash and tensor-arena budgeting, the TFLite Micro C++ setup with MicroMutableOpResolver, and CMSIS-NN acceleration. Use when quantising or converting a model, when deploying to a Cortex-M, STM32, ESP32, Arduino or other MCU, when a model is too large or too slow for a device, when accuracy drops after quantisation, when sizing a tensor arena, or when a TFLite Micro interpreter fails to allocate or invoke. Not for training the model, and not for server-side inference optimisation.
license: MIT
version: 0.1.0
---

# Model to microcontroller

Two things go wrong on this path. The model does not fit, which is a budget
problem you can answer in ten minutes. Or it fits and the accuracy quietly
drops, which is a measurement problem — and usually a calibration-data problem
wearing a disguise.

## Budget first

Write down four numbers before converting anything: flash available, RAM
available for the tensor arena, latency allowed per inference, and the accuracy
you are willing to lose. A model that cannot meet these does not get better
with quantisation tuning, and finding that out now costs ten minutes instead
of a week.

The arena has to hold the largest set of simultaneously live tensors, which is
usually driven by the widest early activation rather than by the weights. A
model that fits flash comfortably can still miss RAM by a factor of three.

## Quantising ONNX

```bash
python3 scripts/quantize_onnx.py model.onnx -o model.int8.onnx \
    --calib data/calibration --compare
```

The script preprocesses (shape inference and folding, skipping which is the
usual cause of "quantisation ran and the model got slower"), calibrates on real
samples, quantises to QDQ format with per-channel weights, and then reports max
absolute difference, cosine similarity and argmax agreement against the float
model. That last part is the point: a quantised model without a measured
accuracy delta is a guess.

For a model that loses too much at int8, `--activation-type uint16
--weight-type int8` recovers most of it at some speed cost.

## Converting for TFLite Micro

```python
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type  = tf.int8
converter.inference_output_type = tf.int8
```

The last two lines are what make the model fully integer. Without them the
converter quantises the interior and leaves float at the boundary, which pulls
the float kernels into the build — flash you did not budget for, and slow on a
core with no FPU. Restricting `supported_ops` to `TFLITE_BUILTINS_INT8` makes
the converter fail loudly on an operator it cannot quantise rather than
silently leaving it in float; a failure there is information.

Then check what you actually got:

```bash
python3 scripts/tflite_report.py model.tflite --resolver
```

It reports whether the model is integer at the boundary, which operators it
uses and whether TFLite Micro has kernels for them, a bracket on the arena
size, and the C++ resolver lines with the right template count.

## Calibration data decides the accuracy

The calibration set sets every activation range in the model, so it matters
more than any other knob. Use 100-500 samples from the real distribution,
including the edge cases you care about — a set with no dark images gives a
model that clips in the dark. Random noise runs fine, reports a size reduction,
and produces junk. Do not calibrate on the test set, or you lose the only
honest measurement you have.

When accuracy drops too far, work in this order: check the calibration data,
because most large drops start there; confirm per-channel weights, since
per-tensor on a conv with varied channel ranges is a frequent cause; find the
one layer losing it by comparing activations layer by layer; widen activations
to uint16; leave the worst layer in float; and only then consider
quantisation-aware training, which recovers the most and costs a training run.

## The C++ side

```cpp
static tflite::MicroMutableOpResolver<4> resolver;   // count must match
resolver.AddConv2D();
resolver.AddMaxPool2D();
resolver.AddFullyConnected();
resolver.AddSoftmax();

static tflite::MicroInterpreter interpreter(model, resolver,
                                            tensor_arena, kTensorArenaSize);
interpreter.AllocateTensors();
printf("arena used: %d\n", (int)interpreter.arena_used_bytes());
```

Register only the operators the model uses; the all-ops resolver costs tens of
kilobytes of flash for kernels that never run. Size the arena generously, then
tighten it to `arena_used_bytes()` — guessing in either direction wastes RAM or
fails allocation on a device you cannot easily debug.

The input tensor is int8 with a scale and zero point recorded in the model, and
the C++ side has to apply the same scaling the training pipeline did. This is
the most common source of "it worked in Python and not on the device".

## Making it fast

Build with CMSIS-NN (`OPTIMIZED_KERNEL_DIR=cmsis_nn`) on Cortex-M4 and above —
several times faster on conv and fully-connected layers, for a compile flag,
and the largest single win available. Compile at `-O2` or more, since a debug
build can be five times slower. Align the arena to 16 bytes and put it in the
fastest RAM the part has. Measure with the cycle counter (`DWT->CYCCNT`), not
with a print and a stopwatch.

Budget tables per MCU class, the full converter recipe, conversion route
trade-offs, and the complete C++ setup are in
[references/deployment-guide.md](references/deployment-guide.md).

## Reporting a deployment result

Six numbers, not one: flash used, arena used, latency per inference, the
accuracy metric on a held-out set, the same metric for the float model, and the
size of that evaluation set. "It fits and it runs" is a hope, not a result.

## Honest limits

`quantize_onnx.py` needs `onnx` and `onnxruntime`. Its `--compare` numbers come
from the calibration set, which the quantiser has already seen, so they detect
gross breakage rather than predicting deployment accuracy — measure the real
metric on a held-out set before shipping. It does not do quantisation-aware
training or mixed-precision layer selection.

`tflite_report.py` needs a TFLite interpreter (`ai-edge-litert`, `tensorflow`
or `tflite-runtime`) and says so if none is installed. Its arena numbers are a
bracket, not an answer: the floor assumes perfect buffer reuse and the ceiling
assumes none. The device's `arena_used_bytes()` is the real number. Its
operator-to-resolver table covers the common TFLite Micro kernels; an operator
missing from that table is reported as unsupported, which may mean the table
needs an entry rather than that the kernel does not exist.

Neither script measures latency or power. Those need the device.
