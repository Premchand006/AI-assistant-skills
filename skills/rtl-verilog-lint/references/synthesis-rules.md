# Synthesisable RTL: the rules behind the checks

Loaded on demand. Each entry says what the construct does in simulation, what
it does after synthesis, and what to write instead.

## Simulation-only constructs

| Construct | Simulation | Synthesis | Write instead |
|---|---|---|---|
| `#5 x <= y;` | waits 5 time units | ignored by Yosys/DC, error in some tools | count clock cycles in an FSM |
| `initial` | runs once at t=0 | ASIC: ignored (flops come up X). FPGA: becomes bitstream init | reset branch in the clocked block |
| `real`, `time` | floating point | rejected | fixed-point on `logic [N-1:0]` |
| `$display`, `$finish` | prints, ends sim | ignored, sometimes warned | wrap in `` `ifndef SYNTHESIS `` |
| `fork`/`join`, `wait` | concurrency | rejected | FSM with explicit states |
| `force`/`release` | overrides a net | rejected | a mux with a debug select |

`` `ifndef SYNTHESIS `` is the portable guard: Yosys, Design Compiler and
Vivado all define `SYNTHESIS` during elaboration.

## Blocking vs non-blocking

The rule is about *simulation determinism*, not about hardware. Both produce
flops; only one produces the same answer every run.

```systemverilog
// Race: the value b sees depends on which always block the simulator picks first.
always_ff @(posedge clk) a = in;
always_ff @(posedge clk) b = a;

// Deterministic: both right-hand sides sample the pre-edge values.
always_ff @(posedge clk) a <= in;
always_ff @(posedge clk) b <= a;
```

Use `<=` in clocked blocks and `=` in combinational blocks. A local temporary
inside a clocked block may use `=` if it is declared and used within that block
only, but the checker flags it because the cost of the rare false positive is
lower than the cost of a missed race.

## Latch inference

A combinational block that does not assign an output on every path holds the
previous value, which is a latch. Latches are not inherently wrong, but an
*accidental* latch breaks static timing analysis and usually means a missing
branch.

```systemverilog
// Infers a latch on y when sel is 2'b10 or 2'b11.
always_comb begin
    case (sel)
        2'b00: y = a;
        2'b01: y = b;
    endcase
end

// Two ways to fix it. Either is fine; pick one per file and stay consistent.
always_comb begin
    y = a;                       // default assignment first
    case (sel)
        2'b01: y = b;
        2'b10: y = c;
        default: ;               // falls through to the default assignment
    endcase
end
```

`always_comb` in SystemVerilog makes the tools check this for you: a latch
inferred inside `always_comb` is an elaboration error in most tools, which is
why it is preferred over `always @(*)`.

## Reset style

```systemverilog
// Asynchronous assert, synchronous release: the common ASIC choice.
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) q <= '0;
    else        q <= d;
end

// Synchronous reset: fewer timing problems on reset release, costs a mux.
always_ff @(posedge clk) begin
    if (!rst_n) q <= '0;
    else        q <= d;
end
```

Every term in an asynchronous sensitivity list needs an edge qualifier. A bare
signal (`always @(posedge clk or rst)`) is a syntax-legal, meaning-free
construct that different tools interpret differently.

Pick one reset style per clock domain. Mixed styles inside one domain make the
reset tree hard to balance and cause reset-recovery violations.

## Multiple drivers

A signal assigned in two procedural blocks becomes two drivers on one net. In
simulation the last writer wins; in synthesis it is an error or a silently
inserted resolution. If two blocks logically need to write a signal, either
merge them or give each its own signal and mux the results.

## `default_nettype`

Without `` `default_nettype none ``, a misspelled signal name becomes an
implicitly declared 1-bit wire. The bug then shows up as a width mismatch three
modules away. Put `` `default_nettype none `` at the top of each file and
`` `default_nettype wire `` at the bottom, so the setting does not leak into
files compiled after yours.

## Width and sign

* Verilog widens operands to the width of the widest operand *in the
  assignment*, including the left-hand side. `assign y8 = a4 * b4;` keeps only
  8 bits; `assign y8 = (a4 * b4) >> 2;` truncates before you see the result.
* Mixing `signed` and `unsigned` in one expression makes the whole expression
  unsigned. Cast explicitly: `$signed(a) * $signed(b)`.
* An unsized literal (`1`, `0`) is 32 bits. Use `'0`, `'1`, or a sized literal
  (`8'd1`) in RTL.

## Arithmetic that costs more than it looks

* `/` and `%` by a non-power-of-two synthesise a divider: large, slow, and
  usually the critical path. Use a shift, a reciprocal multiply, or a
  multi-cycle divider block with a ready/valid handshake.
* A comparison chain in one `always_comb` becomes a priority encoder with depth
  equal to the number of branches. A `case` with mutually exclusive branches
  becomes a mux, which is faster.

## FPGA versus ASIC

| Topic | FPGA | ASIC |
|---|---|---|
| `initial` values | honoured in the bitstream | ignored; use reset |
| Inferred RAM | maps to BRAM given the right coding style | needs a compiled macro, instantiated |
| Gated clocks | avoid; use clock enables | use a clock-gating cell, inserted by the tool |
| Tri-state internal | not available | avoid; only for top-level pads |

Ask which target you are on before choosing a memory or reset style. The same
RTL can be right for one and wrong for the other.
