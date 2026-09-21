# Self-checking testbench patterns

Loaded on demand. Working skeletons for the two stacks worth defaulting to.

## SystemVerilog skeleton

Everything a regression test needs and nothing it does not: a clock, a reset
task, a watchdog, an error counter, and an exit status that reflects the
result.

```systemverilog
`timescale 1ns/1ps

module fifo_tb;
    localparam int CLK_PERIOD = 10;
    localparam int TIMEOUT_NS = 100_000;

    logic clk = 0, rst_n = 0;
    int   errors = 0;
    int   checks = 0;

    always #(CLK_PERIOD/2) clk = ~clk;

    // Watchdog: a hung DUT fails instead of blocking the runner forever.
    initial begin
        #TIMEOUT_NS;
        $error("TIMEOUT after %0d ns", TIMEOUT_NS);
        $fatal(1);
    end

    // Waveforms only when asked; dumping every run is slow.
    initial if ($test$plusargs("waves")) begin
        $dumpfile("fifo_tb.vcd");
        $dumpvars(0, fifo_tb);
    end

    fifo #(.WIDTH(8), .DEPTH(16)) dut (.*);

    task automatic check(input string what, input logic [7:0] got, exp);
        checks++;
        if (got !== exp) begin
            errors++;
            $error("%s: got %h expected %h at %0t", what, got, exp, $time);
        end
    endtask

    task automatic reset();
        rst_n = 0;
        repeat (3) @(posedge clk);
        rst_n <= 1;
        @(posedge clk);
    endtask

    initial begin
        reset();
        // Drive on the inactive edge so the DUT samples settled values.
        @(negedge clk);
        // ... stimulus, each with a check() ...

        if (errors != 0) begin
            $display("FAIL: %0d error(s) in %0d check(s)", errors, checks);
            $fatal(1);
        end
        $display("PASS: %0d check(s)", checks);
        $finish;
    end
endmodule
```

Details that decide whether this works in CI:

- `$finish` exits 0. A failing test that ends in `$finish` is a green build.
  End a failing run with `$fatal(1)`.
- Drive stimulus on the opposite edge from the one the DUT samples. Driving on
  the same edge with a blocking assignment races the DUT, and whether it works
  depends on the simulator.
- Print the seed on every run, so a random failure can be replayed.
- `checks` matters as much as `errors`. Zero errors out of zero checks is the
  most common false pass there is.

## Concurrent assertions

Assertions catch protocol violations continuously, without you writing a
checker that samples at the right moment.

```systemverilog
// Never write to a full FIFO.
assert property (@(posedge clk) disable iff (!rst_n)
    full |-> !push)
    else $error("push while full");

// Every request gets an ack within 16 cycles.
assert property (@(posedge clk) disable iff (!rst_n)
    req |-> ##[1:16] ack)
    else $error("request not acknowledged in 16 cycles");

// Data is stable while valid is high and ready is low.
assert property (@(posedge clk) disable iff (!rst_n)
    (valid && !ready) |=> $stable(data))
    else $error("data changed during a stalled beat");
```

`disable iff (!rst_n)` is not optional: without it every assertion fires during
reset and the log fills with noise that hides the real failure.

Put assertions in the design file, bound with `bind`, or in a separate checker
module. Assertions inside the DUT travel with it into every testbench that
instantiates it, which is usually what you want.

## cocotb skeleton

```python
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge


async def reset(dut, cycles=3):
    dut.rst_n.value = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@cocotb.test(timeout_time=100, timeout_unit="us")
async def test_fifo_roundtrip(dut):
    seed = int(os.environ.get("SEED", random.randrange(2**32)))
    random.seed(seed)
    dut._log.info("seed=%d", seed)          # replay a failure with SEED=...

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset(dut)

    model = []
    for _ in range(100):
        await FallingEdge(dut.clk)          # drive on the inactive edge
        if random.random() < 0.6 and not dut.full.value:
            value = random.randrange(256)
            dut.din.value = value
            dut.push.value = 1
            model.append(value)
        else:
            dut.push.value = 0

        if model and random.random() < 0.5 and not dut.empty.value:
            dut.pop.value = 1
            await RisingEdge(dut.clk)
            expected = model.pop(0)
            assert dut.dout.value == expected, \
                f"got {int(dut.dout.value)} expected {expected}"
        else:
            dut.pop.value = 0
```

`timeout_time` on the decorator is what keeps a hung DUT from blocking the
runner. cocotb reports a test as passing unless an assertion raises, so a test
with no assertion always passes.

The `model` list is a scoreboard: a reference implementation simple enough to
be obviously correct, compared against the DUT on every transaction. That is
the pattern that scales — checking outputs against hand-written expected values
stops being maintainable at about twenty cases.

## Coverage

Coverage answers a question the pass/fail result cannot: what did the tests
never reach?

```systemverilog
covergroup cg_fifo @(posedge clk);
    option.per_instance = 1;
    cp_level: coverpoint level {
        bins empty    = {0};
        bins low      = {[1:3]};
        bins mid      = {[4:12]};
        bins high     = {[13:15]};
        bins full     = {16};
    }
    cp_op: coverpoint {push, pop} {
        bins idle = {2'b00};
        bins wr   = {2'b10};
        bins rd   = {2'b01};
        bins both = {2'b11};
    }
    x_level_op: cross cp_level, cp_op;
endcovergroup
```

The cross is where the value is. Hitting "full" and hitting "simultaneous push
and pop" separately says nothing about what happens when both are true, which
is exactly where the bug is.

Aim coverage at states the specification cares about, not at line coverage.
100% line coverage with 40% functional coverage is a well-exercised
implementation of an untested specification.

## What "the tests pass" is worth

A green run says the checks that exist did not fail. Before treating it as
evidence, know: how many checks ran, what the functional coverage was, whether
reset and error paths were exercised, and whether the run was seeded randomly
or ran one fixed path. A testbench that reports "PASS: 0 checks" is the failure
mode this whole page exists to prevent.
