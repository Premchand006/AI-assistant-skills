---
name: rtl-verilog-lint
description: Write and review synthesisable Verilog and SystemVerilog RTL, and check it before it reaches a synthesis tool. Covers blocking vs non-blocking assignments, latch inference, reset style, sensitivity lists, multiple drivers, width and sign rules, and simulation-only constructs that do not synthesise. Use when writing, reviewing, refactoring or debugging .v/.sv/.svh design files, when a module has to pass lint or synthesis, when Yosys, Verilator, Verible, Vivado or Design Compiler reports an elaboration error, or when RTL simulates correctly but behaves differently after synthesis. Not for testbench structure or coverage, which belong to rtl-testbench-discipline, and not for timing or clock-domain crossing, which belong to timing-closure-cdc.
license: MIT
version: 0.1.0
---

# Synthesisable RTL

The failure this skill exists to prevent: RTL that simulates cleanly, passes a
casual review, and then either fails elaboration or synthesises into different
hardware than the code appears to describe. Those bugs are cheap to prevent in
the source and expensive to find in a netlist.

## Order of work

1. Ask for the target if it is not in the repo: FPGA or ASIC, and which
   family or PDK. Reset style, memory inference and clock gating differ, and
   the answer changes what correct code looks like.
2. Write or edit the RTL following the rules below.
3. Run `scripts/check_synthesizable.py` on the files you touched.
4. Run `scripts/lint_rtl.sh` for the full pass, which adds Verilator, Verible
   and a Yosys elaboration when those tools are installed.
5. Report what ran and what did not. A clean result from two installed tools
   is not the same as a clean result from a full flow, and saying so keeps the
   next person from trusting it too far.

```bash
python3 scripts/check_synthesizable.py rtl/ --exclude "*_tb.sv"
./scripts/lint_rtl.sh --top my_design rtl/
```

The checker exits non-zero on any error-severity finding, so it drops into a
pre-commit hook or a CI job unchanged.

## The rules that catch the most bugs

**Non-blocking in clocked blocks, blocking in combinational blocks.** `always_ff`
with `=` creates a simulation race whose outcome depends on the order the
simulator schedules blocks; the netlist and the waveform then disagree.

```systemverilog
always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) q <= '0;
    else        q <= d;      // <= here
end

always_comb begin
    y = a & b;               // = here
end
```

**Assign every output on every path through a combinational block.** A branch
that leaves an output unassigned infers a latch, which breaks static timing
analysis and usually means a forgotten case. Assign defaults at the top of the
block, or give every `case` a `default`. Prefer `always_comb` over
`always @(*)`: tools report an inferred latch inside `always_comb` as an error.

**Every term in an async sensitivity list needs an edge.**
`always @(posedge clk or negedge rst_n)` is a flop with async reset.
`always @(posedge clk or rst)` is legal syntax with no agreed meaning, and
different tools resolve it differently.

**One signal, one procedural block.** Two `always` blocks writing one signal is
two drivers on one net: last-writer-wins in simulation, an error or a silent
resolution in synthesis.

**`` `default_nettype none `` at the top of every file**, `` `default_nettype
wire `` at the bottom. Without it a misspelled name becomes an implicit 1-bit
wire and the bug surfaces as a width mismatch somewhere else.

**Size your literals and watch the widths.** Verilog widens to the widest
operand in the assignment, the left-hand side included, so `y8 = a4 * b4` keeps
only the low 8 bits. An unsized `1` is 32 bits; write `'0`, `'1` or `8'd1`.
Mixing signed and unsigned makes the whole expression unsigned, so cast with
`$signed()` when you mean signed arithmetic.

**Keep simulation constructs out of the design.** Delays, `initial`, `real`,
`time`, `fork`/`join` and `wait` either vanish or fail at synthesis. Debug
output belongs behind `` `ifndef SYNTHESIS ``, which every major tool defines
during elaboration.

**Watch what the arithmetic costs.** `/` and `%` by a non-power-of-two build a
divider that usually becomes the critical path. A long if/else chain builds a
priority encoder; a `case` over mutually exclusive conditions builds a mux.

Worked examples, the FPGA-versus-ASIC differences, and the reasoning behind
each rule are in [references/synthesis-rules.md](references/synthesis-rules.md).
Read it when a rule needs justifying to a reviewer or when the target platform
is in question.

## Reviewing someone else's RTL

Run the checker first so the mechanical findings are already on the table, then
read for the things no checker sees:

- Does the reset actually reach every state element that needs it, and is the
  style consistent within the clock domain?
- Are FSM state encodings and transitions exhaustive, with a defined recovery
  from illegal states?
- Do handshakes hold data stable while `valid` is high, and does `ready` not
  depend combinationally on `valid` in a way that forms a loop?
- Are memory read latencies in the RTL the same as in the memory being
  instantiated?
- Do parameter values get checked, so an out-of-range parameter fails
  elaboration rather than producing broken hardware?

Signals crossing between clocks are out of scope here; hand those to
`timing-closure-cdc`, which checks synchroniser structure.

## Honest limits

`check_synthesizable.py` works on the text after comments and strings are
stripped. It does not elaborate the design, expand macros, resolve `include`
files or understand generate blocks, so it misses defects inside macros and
can misread unusual formatting. It is a fast first pass whose value is that it
runs in a second with no tool installation; Verilator, Verible and Yosys
elaboration remain the real checks, and synthesis is the only authority on what
the hardware becomes.

Findings are reported at three severities. `error` means the construct is
rejected or silently changes meaning at synthesis. `warn` means it is legal but
is a common source of bugs. `info` is an area or timing cost worth a look.
