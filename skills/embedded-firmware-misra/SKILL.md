---
name: embedded-firmware-misra
description: Write and review bare-metal or RTOS firmware in C for microcontrollers such as STM32, Cortex-M, AVR, ESP32 and RISC-V MCUs. Covers interrupt handler discipline, volatile and atomicity on state shared with an ISR, critical sections, ring buffers, memory-mapped register access, stack bounding, static analysis with cppcheck and clang-tidy, and the MISRA C:2012 rules that prevent real defects. Use when writing or reviewing .c or .h firmware, an IRQ handler, a peripheral driver, a HAL or register header, FreeRTOS or Zephyr task code, when a device works on the bench but fails intermittently in the field, or when a build needs static analysis or MISRA justification.
license: MIT
version: 0.1.0
---

# Firmware that survives the field

The bugs that matter here are the ones that depend on when an interrupt lands.
They pass every test on the bench, then fail once a week in a product that has
already shipped. Most of them come from three mistakes: state shared with an
interrupt that is not `volatile`, a read-modify-write on shared state with no
critical section, and a handler that blocks.

```bash
python3 scripts/check_isr_safety.py src/ --fail-on error
./scripts/run_static.sh --misra src/          # adds cppcheck and clang-tidy
```

The checker finds interrupt handlers, works out which globals they share with
the rest of the program, and reports the unsafe shares.

## volatile is not atomicity

`volatile` stops the compiler caching a variable in a register. That is all it
does, and it is not enough for anything that reads then writes:

```c
volatile uint32_t count;

count = 0;      /* safe: a single store */
x = count;      /* safe: a single load  */
count++;        /* broken: load, add, store - an interrupt between them loses an update */
```

Three ways out, in order of preference:

```c
/* 1. Make the ISR the only writer. A single-producer single-consumer ring
      buffer with a power-of-two mask needs no critical section at all. */
/* ISR:  buf[head] = byte; head = (head + 1u) & MASK;   */
/* main: while (tail != head) { use(buf[tail]); tail = (tail + 1u) & MASK; } */

/* 2. C11 atomics, where the toolchain has them. */
atomic_fetch_add(&count, 1);

/* 3. The shortest possible critical section, saving and restoring PRIMASK. */
uint32_t primask = __get_PRIMASK();
__disable_irq();
count++;
__set_PRIMASK(primask);
```

Ending a critical section with `__enable_irq()` rather than restoring PRIMASK
enables interrupts even when the caller had deliberately disabled them. That
bug is invisible until the day it is not.

## Interrupt handlers

A handler makes the event safe to deal with later: read the register that must
be read, store the data, set a flag, return. Not in a handler: `printf`,
`malloc` or `free`, `HAL_Delay`, blocking RTOS calls whose name lacks
`FromISR`, floating point on a core where it costs context, and any loop
without a bound.

Two Cortex-M details worth knowing: a peripheral flag cleared on the last line
of a handler may not reach the NVIC before the handler returns, which causes a
spurious re-entry — clear it early; and numerically lower priority numbers are
more urgent, so a long handler at high priority adds jitter to everything else.

## Registers

```c
typedef struct {
    volatile uint32_t SR;
    volatile uint32_t DR;
} uart_regs_t;
#define UART ((uart_regs_t *)0x40011000UL)
```

`REG |= BIT;` on a register with write-1-to-clear bits reads the register, sets
one bit, and writes the whole value back — clearing every pending flag that
happened to be set. Write the bit on its own. And do not describe register
layouts with bit-fields: the standard fixes neither the bit order nor the
access width.

## Bounding the stack

There is no virtual memory, so an overflow quietly corrupts whatever is next in
RAM. No recursion, no variable-length arrays, no `alloca`, and no heap after
initialisation. Fill the stack with a pattern at boot and check the high-water
mark, or put an MPU guard region below it. `-fstack-usage` gives per-function
numbers that a script can sum along the call graph for a worst-case bound.

## MISRA, proportionately

Full MISRA C:2012 compliance needs a certified checker and a deviation process.
Outside a certified project, the rules that repay the effort are Dir 4.12 and
21.3 (no dynamic memory), 17.2 (no recursion), 10.x (no implicit conversions),
16.x (`switch` has a default and every case breaks), and 20.7 (parenthesise
macro parameters). Those catch real defects. Rule 15.5, one return per
function, is advisory and widely deviated.

When a project claims MISRA compliance, ask which checker, which rule set
version, and where the deviation records are. Without those three, the claim is
decorative.

Working code for critical sections, ring buffers, wide shared reads, register
access, the stack-bounding techniques and the full rule table are in
[references/concurrency-and-memory.md](references/concurrency-and-memory.md).

## Build flags

```
-Wall -Wextra -Wshadow -Wconversion -Wdouble-promotion
-Wformat=2 -Wundef -fno-common -Werror -fstack-usage
```

`-Wconversion` is the noisy one, and the one that finds real integer bugs.
Silencing a warning is a decision to record in the code, not a flag to quietly
drop from the build.

## Honest limits

`check_isr_safety.py` analyses one file at a time with regular expressions
after stripping comments and strings. It does not preprocess, so it misses
handlers and shared state that come from macros, and it does not follow calls
between translation units — a variable shared through an accessor function in
another file will not be seen. It identifies handlers by naming convention
(`*_IRQHandler`, `*_Handler`, `*_ISR`) and by the `interrupt` attribute; a
handler registered another way is invisible to it.

A clean run means no unsafe share was found in the files given, in the shapes
the checker recognises. Real timing bugs need a logic analyser, stress at
temperature, and a long soak. cppcheck, clang-tidy and the compiler at
`-Wall -Wextra` remain the tools that see the whole translation unit.
