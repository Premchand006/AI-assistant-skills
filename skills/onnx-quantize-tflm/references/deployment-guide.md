# From a trained model to a microcontroller

Loaded on demand.

## The budget decides everything

Before any conversion, write down four numbers. If the model does not fit, no
amount of quantisation tuning will save it, and you will find that out after a
week of work instead of in ten minutes.

| Budget | Where it goes | How to measure |
|---|---|---|
| Flash | model weights + TFLM kernels + your code | `arm-none-eabi-size` on the linked binary |
| RAM | tensor arena + stack + everything else | `interpreter.arena_used_bytes()` |
| Latency | one inference | cycle counter (DWT->CYCCNT on Cortex-M) |
| Energy | inference plus duty cycle | current meter, averaged over a duty cycle |

Rough ceilings, as a sanity check rather than a rule:

| Class | Flash | RAM | Realistic model |
|---|---|---|---|
| Cortex-M0+ | 32-256 KB | 4-32 KB | small MLP, decision tree |
| Cortex-M4F | 256KB-1MB | 64-256 KB | small CNN, keyword spotting |
| Cortex-M7 / M33 | 1-2 MB | 256KB-1MB | MobileNet-class with care |
| MCU + accelerator (Ethos-U) | as above | as above | a few MB of int8 |

The arena has to hold the largest set of simultaneously live tensors, which is
usually driven by the widest early activation, not by the weights. A model can
fit flash easily and still not fit RAM.

## Two routes

**PyTorch -> ONNX -> ONNX Runtime**, if the target runs ONNX Runtime (Linux
class, or a vendor runtime that accepts ONNX). Quantise with `quantize_static`
in QDQ format.

**TensorFlow/Keras -> TFLite -> TFLite Micro**, if the target is a bare-metal
MCU. This is the well-trodden path for Cortex-M.

**PyTorch -> ONNX -> TFLite** via `onnx2tf` works, but the conversion inserts
transposes for the NCHW-to-NHWC change, and those cost both latency and arena.
Check the converted graph rather than assuming it is equivalent.

## Full integer quantisation for TFLite

```python
import tensorflow as tf

def representative_dataset():
    # 100-500 samples from the real input distribution. Not random noise:
    # the calibration data sets every activation range in the model.
    for sample in calibration_samples[:200]:
        yield [sample.astype("float32")]

converter = tf.lite.TFLiteConverter.from_saved_model(saved_model_dir)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.int8      # int8 in
converter.inference_output_type = tf.int8     # int8 out
tflite_model = converter.convert()
```

Setting `inference_input_type` and `inference_output_type` is what makes the
model fully integer. Without them the converter quantises the interior and
leaves float at the boundary, which drags the float kernels into the build —
flash you did not budget for, and slow on a core without an FPU.

`target_spec.supported_ops = [TFLITE_BUILTINS_INT8]` makes the converter fail
loudly on an operator it cannot quantise, instead of silently leaving it in
float. A failure here is information, not an obstacle.

## Calibration data

The calibration set determines every activation range in the model, so it has
more effect on accuracy than any other knob.

- 100-500 samples is the usual range. More rarely helps; fewer than about 50 is
  visibly noisy.
- Draw from the real distribution, including the edge cases you care about. A
  set with no dark images gives you a model that clips in the dark.
- Random noise as calibration data produces ranges unrelated to deployment. It
  runs, it reports a size reduction, and the accuracy is junk.
- Do not calibrate on the test set. The numbers you get back will be optimistic
  and you will have lost your only honest measurement.

## When accuracy drops too far

In order of what to try:

1. **Check the calibration data first.** Most large drops are a calibration
   problem, not a quantisation problem.
2. **Per-channel weights.** On by default in `quantize_static`; for TFLite it is
   the default for conv layers. Per-tensor weights on a conv with varied
   channel ranges is a common cause of a large drop.
3. **Find the layer that is losing it.** Compare activations layer by layer
   between the float and quantised models. It is usually one layer, often the
   first or an attention-like operation with a wide dynamic range.
4. **Wider activations.** `uint16` activations with `int8` weights recovers most
   of the loss at some speed cost, where the runtime supports it.
5. **Leave one layer in float.** A mixed-precision model with the worst layer
   in float is often the practical answer.
6. **Quantisation-aware training.** Recovers the most, costs a training run.
   Worth it when the model is going into volume.

## The C++ side (TFLite Micro)

```cpp
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "model_data.h"     // xxd -i model.tflite > model_data.h

constexpr int kTensorArenaSize = 32 * 1024;
alignas(16) static uint8_t tensor_arena[kTensorArenaSize];

void setup() {
    const tflite::Model* model = tflite::GetModel(g_model_data);
    if (model->version() != TFLITE_SCHEMA_VERSION) { /* fail loudly */ }

    // Only the operators this model uses. The all-ops resolver costs tens of
    // kilobytes of flash for kernels that never run.
    static tflite::MicroMutableOpResolver<4> resolver;
    resolver.AddConv2D();
    resolver.AddMaxPool2D();
    resolver.AddFullyConnected();
    resolver.AddSoftmax();

    static tflite::MicroInterpreter interpreter(
        model, resolver, tensor_arena, kTensorArenaSize);
    if (interpreter.AllocateTensors() != kTfLiteOk) { /* arena too small */ }

    // Now tighten the arena to what it actually used.
    printf("arena used: %d\n", (int)interpreter.arena_used_bytes());
}

void infer(const float* input, int len) {
    TfLiteTensor* in = interpreter.input(0);
    // Apply the same quantisation the converter recorded.
    for (int i = 0; i < len; i++) {
        in->data.int8[i] = (int8_t)roundf(input[i] / in->params.scale)
                           + in->params.zero_point;
    }
    if (interpreter.Invoke() != kTfLiteOk) { /* handle */ }

    TfLiteTensor* out = interpreter.output(0);
    float y = (out->data.int8[0] - out->params.zero_point) * out->params.scale;
}
```

`scripts/tflite_report.py --resolver` generates the resolver lines and the op
count from the model, which is how you avoid the two mistakes here: an op
resolver template argument that does not match the number of registered ops,
and a missing operator that shows up as a runtime failure in
`AllocateTensors()`.

## Making it fast

1. **Build with CMSIS-NN.** On Cortex-M4 and above this is the single largest
   win available — several times faster on conv and fully-connected layers, for
   a compile flag. TFLM's `OPTIMIZED_KERNEL_DIR=cmsis_nn`.
2. **Compile at `-O2` or `-O3`.** A debug build can be five times slower, and
   more than one "TFLM is too slow" report has turned out to be `-O0`.
3. **Align the arena to 16 bytes.** Unaligned arenas cost cycles on every
   access, and on some cores fault.
4. **Put the arena in the fastest RAM.** On an STM32H7, DTCM rather than
   AXI SRAM is worth a large fraction of the runtime.
5. **Measure with the cycle counter**, not with a wall clock and a print. Enable
   `DWT->CYCCNT` and read it either side of `Invoke()`.

## Reporting a result

A deployment result needs six numbers, not one: flash used, arena used, latency
per inference, the accuracy metric on a held-out set, the same metric for the
float model, and the size of the evaluation set. "It fits and it works" is not
a result; it is a hope.
