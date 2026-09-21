# Shared state, memory maps and MISRA in firmware

Loaded on demand.

## volatile: what it does and what it does not

`volatile` tells the compiler that a variable can change outside the visible
control flow, so it must not cache it in a register or optimise the access
away. That is all it does.

```c
volatile uint32_t tick_ms;     /* written by SysTick, read by main: correct */

/* Still broken, even though tick_ms is volatile: */
if (tick_ms - start > TIMEOUT) { ... }   /* fine, single read           */
count++;                                  /* NOT fine, read-modify-write */
```

`count++` on a shared variable compiles to load, add, store. An interrupt
landing between the load and the store loses its update. `volatile` guarantees
the load and store happen; it guarantees nothing about them being one
operation.

What to use instead:

```c
/* Cortex-M: shortest correct critical section */
uint32_t primask = __get_PRIMASK();
__disable_irq();
count++;
__set_PRIMASK(primask);          /* restores, rather than blindly enabling */

/* C11 atomics, where the toolchain supports them */
#include <stdatomic.h>
atomic_uint_least32_t count;
atomic_fetch_add(&count, 1);

/* Often best: make the ISR the only writer */
/* ISR:  buf[head] = byte; head = (head + 1u) & MASK;   */
/* main: while (tail != head) { use(buf[tail]); tail = (tail + 1u) & MASK; } */
```

That last one is a single-producer single-consumer ring buffer. With one
writer per index and a power-of-two mask, no critical section is needed at all,
which is why it is the standard structure for a UART driver.

`__enable_irq()` at the end of a critical section is a bug waiting to happen:
if the caller had interrupts disabled, you have just enabled them. Save and
restore PRIMASK instead.

## Reading a shared value that is wider than the bus

On a 32-bit core, a 64-bit read is two instructions. An interrupt between them
returns half of an old value and half of a new one. Read it twice and compare,
or take a critical section:

```c
static uint64_t read_tick64(void)
{
    uint64_t a, b;
    do { a = tick64; b = tick64; } while (a != b);
    return a;
}
```

## Interrupt handlers

The handler's job is to make the event safe to handle later: read the hardware
register that needs reading, put the data somewhere, set a flag, return.

| Do not | Because |
|---|---|
| `printf` | blocks for milliseconds and is not reentrant |
| `malloc` / `free` | take a lock and can deadlock against the main loop |
| `HAL_Delay` | busy-waits on a tick that a handler at the same or higher priority cannot advance |
| FreeRTOS non-`FromISR` API | blocking calls are not allowed in an ISR |
| Floating point | on M4F, 17 extra words of context per entry; on M0, a software library call |
| Unbounded `while` | starves every interrupt at or below that priority |

On Cortex-M, a peripheral flag cleared on the last line of the handler may not
have reached the NVIC before the handler returns, causing a spurious re-entry.
Clear the flag early, then read back once (`__DSB()`) if the handler is short.

Handler priorities matter as much as handler contents: a lower-priority handler
cannot pre-empt a higher one, so a long handler at high priority adds jitter to
everything. On Cortex-M, numerically lower priority values are more urgent.

## Memory-mapped registers

```c
/* Correct: volatile, unsigned, exact width */
#define UART_BASE   (0x40011000UL)
typedef struct {
    volatile uint32_t SR;
    volatile uint32_t DR;
    volatile uint32_t BRR;
} uart_regs_t;
#define UART ((uart_regs_t *)UART_BASE)
```

Three mistakes that cost a debugging session each:

- **A missing `volatile`** on a register struct. The compiler removes the second
  read of a status register, so polling loops forever on a stale value.
- **Read-modify-write on a register with write-1-to-clear bits.**
  `REG |= BIT;` reads the register, sets the bit, and writes everything back,
  clearing every W1C flag that happened to be set. Write the bit alone.
- **Bit-fields for register layouts.** The standard does not fix the bit order,
  the width, or the access size. Use masks and shifts.

## Stack and determinism

Firmware has no virtual memory and usually no MMU, so a stack overflow silently
corrupts whatever is next in RAM.

- No recursion: there is no static bound on the depth (MISRA C:2012 Rule 17.2).
- No variable-length arrays and no `alloca`, for the same reason.
- No heap after initialisation, and preferably none at all: fragmentation gives
  no bound on allocation failure (MISRA Dir 4.12, Rule 21.3).
- Fill the stack with a pattern at boot and check the high-water mark, or use
  the MPU to put a guard region below it.
- `-fstack-usage` gives per-function stack usage, which a script can sum along
  the call graph for a worst-case bound.

## MISRA C:2012, proportionately

MISRA is a coding standard for safety-related C. Full compliance requires a
certified checker and a deviation process. If you are not in a certified
project, the subset that prevents real bugs:

| Rule | What it says | Why |
|---|---|---|
| Dir 4.12 / 21.3 | no dynamic memory | no bound on failure or fragmentation |
| 17.2 | no recursion | no bound on stack |
| 8.4 / 8.7 | declare before use, `static` where possible | catches accidental external linkage |
| 10.x | no implicit type conversions | integer promotion surprises |
| 14.4 | controlling expressions are boolean | `if (x = 0)` and `if (ptr)` |
| 15.5 | one return per function | advisory; readability, disputed |
| 15.6 | braces on every `if`/`for`/`while` | the goto fail bug |
| 16.x | `switch` has a default, every case breaks | fallthrough bugs |
| 20.7 | parenthesise macro parameters | precedence at the call site |
| 21.x | no `stdio`, `stdlib`, `string` in production | size, reentrancy, unbounded behaviour |

The rules with the best cost-to-benefit ratio outside a certified project are
10.x (implicit conversions), 16.x (switch) and 20.7 (macros). Those three catch
real defects. Rule 15.5 is advisory and widely deviated.

`cppcheck --addon=misra` gives rule numbers; the rule texts are licensed
separately, so findings show numbers without text unless you supply
`--rule-texts`.

## Compiler flags that pay for themselves

```
-Wall -Wextra -Wshadow -Wconversion -Wdouble-promotion
-Wformat=2 -Wundef -fno-common -Werror
-ffunction-sections -fdata-sections -Wl,--gc-sections
-fstack-usage
```

`-Wconversion` is noisy on existing code and is the one that finds real integer
bugs. `-fno-common` turns a duplicate definition into a link error instead of a
silent merge. Turning a warning off is a decision to record in the file, not a
flag to drop from the build.
