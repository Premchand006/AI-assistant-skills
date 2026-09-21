---
name: rtl-testbench-discipline
description: Write and review hardware testbenches that decide pass or fail by themselves. Covers self-checking structure with scoreboards and error counters, watchdog timeouts, SystemVerilog assertions, functional coverage, constrained random stimulus with reproducible seeds, cocotb testbenches, and UVM agent, phase and sequence structure. Use when writing or reviewing a testbench, a cocotb test, a UVM environment, an SVA property or a covergroup, when a simulation passes but the hardware does not work, when a test hangs or exits zero after failing, or when deciding how much verification a block needs. Not for the design RTL itself, which belongs to rtl-verilog-lint.
license: MIT
version: 0.1.0
---

# Testbenches that can fail

A testbench that prints signals for a human to read is a demo. A testbench that
decides pass or fail, cannot hang, and says why it failed is a regression test.
The gap between them is where "simulation was clean" comes from on a design
that does not work.

```bash
python3 scripts/check_testbench.py tb/ --fail-on error
```

The checker handles SystemVerilog and cocotb, and looks for testbenches that
cannot fail: no assertion or comparison anywhere, no watchdog, an exit status
that ignores the result, stimulus racing the clock edge the DUT samples on.

## The five properties

**It checks.** Compare against an expected value from a reference model, not
against a value copied out of a previous waveform. A scoreboard — a model
simple enough to be obviously correct, compared on every transaction — scales
past the twenty-case mark where hand-written expected values stop being
maintainable.

**It counts what it checked.** Zero errors out of zero checks is the most
common false pass in hardware verification. Report both, and fail a run where
the check count is zero.

**It cannot hang.** A watchdog that calls `$fatal` after a bounded time, or
`timeout_time` on `@cocotb.test()`. Without it, a DUT that never asserts `done`
blocks a CI runner until someone notices.

**Its exit status is the result.** `$finish` exits 0, so a failing test that
ends in `$finish` is a green build. End failing runs with `$fatal(1)`. In UVM,
set `set_report_max_quit_count(1)` so `UVM_ERROR` fails the run.

**Its failures reproduce.** Print the seed on every run and accept it from the
environment, so a random failure can be replayed exactly.

## Not racing the DUT

Drive stimulus on the opposite edge from the one the DUT samples:

```systemverilog
@(negedge clk);
din <= 8'hA5;      // DUT sees a settled value at the next posedge
```

Driving with a blocking assignment on the same edge the DUT samples makes the
result depend on which process the simulator schedules first, so the testbench
passes on one simulator and fails on another. A SystemVerilog `clocking` block
in the interface removes the race for the whole testbench at once.

## Assertions

Assertions check continuously, without you finding the right moment to sample:

```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
    (valid && !ready) |=> $stable(data))
    else $error("data changed during a stalled beat");
```

`disable iff (!rst_n)` is what keeps the log readable — without it every
assertion fires during reset and buries the real failure. Put assertions in the
interface or `bind` them to the DUT, so they run in every testbench that uses
it, at block level and chip level alike.

## Choosing the stack

| Situation | Use |
|---|---|
| One module, a few directed cases | plain SystemVerilog with an error counter |
| Protocol interface, open-source tools | cocotb with a scoreboard, or SVA |
| Reusable IP, many tests, a team | UVM |

UVM costs about a thousand lines of infrastructure before the first check runs,
and needs a simulator that supports it — Verilator and Icarus do not. For a
FIFO that is a bad trade; for an AXI slave three teams will instantiate, it is
the cheapest option available.

Working skeletons for SystemVerilog and cocotb, the scoreboard pattern, and
covergroup examples are in
[references/selfchecking-patterns.md](references/selfchecking-patterns.md).
UVM agent structure, the objection and factory mistakes that produce a test
which silently does nothing, and a review checklist are in
[references/uvm-discipline.md](references/uvm-discipline.md).

## Coverage

Coverage answers what the pass/fail result cannot: what the tests never
reached. Aim it at states the specification cares about, and cross the
coverpoints — hitting "FIFO full" and hitting "simultaneous push and pop"
separately says nothing about the case where both are true, which is where the
bug is. 100% line coverage with 40% functional coverage is a well-exercised
implementation of an untested specification.

## Reporting a result honestly

When reporting that tests pass, say how many checks ran, what coverage was
reached, and whether reset and error paths were exercised. "The tests pass"
without those numbers is not evidence, and the checker prints them for exactly
this reason.

## Honest limits

`check_testbench.py` is structural. It finds testbenches that cannot fail; it
cannot tell whether a testbench that does check is checking the right thing,
whether the reference model is correct, or whether the stimulus reaches the
interesting states. A testbench can pass every check here and verify nothing
useful. Coverage numbers and a review against the specification are what close
that gap.
