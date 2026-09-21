---
name: timing-closure-cdc
description: Diagnose static timing analysis failures and clock-domain crossings in digital designs. Covers reading setup and hold reports from OpenSTA, OpenROAD, PrimeTime or Vivado, deciding whether a violation is a logic, clock-tree or constraint problem, writing SDC constraints, and choosing the right crossing structure among two-flop synchroniser, toggle synchroniser, gray code, handshake, async FIFO and reset synchronisation. Use when a design fails setup or hold, when slack is negative, when a design has more than one clock, when a signal moves between clock domains, when writing or fixing an SDC file, or when hardware behaves intermittently in a way simulation does not reproduce.
license: MIT
version: 0.1.0
---

# Timing and clock-domain crossings

Two failure modes, related by the fact that static timing analysis cannot see
the second one. A timing violation is visible, reproducible and gets fixed. A
missing synchroniser passes RTL simulation, passes STA, and shows up as a
machine that hangs once a week.

## Clock-domain crossings

```bash
python3 scripts/cdc_scan.py rtl/ --fail-on error
```

The scanner infers each signal's domain from the always block that writes it,
propagates through combinational logic, and reports every read in a different
domain along with what synchronisation it found: none, one flop, two flops on a
multi-bit bus, or a correct two-flop synchroniser.

Pick the structure by what the signal is, because a two-flop synchroniser is
the right answer for exactly one of these:

| What crosses | Pattern |
|---|---|
| Single-bit level | two-flop synchroniser |
| Single-bit pulse | toggle synchroniser |
| Multi-bit, one bit changes at a time | gray code, then synchronise |
| Multi-bit data, arbitrary values | handshake with data held stable, or async FIFO |
| Streaming data | async FIFO with gray-coded pointers |
| Reset | async assert, sync de-assert, one per domain |

```systemverilog
logic meta, sync;
always_ff @(posedge clk_dst or negedge rst_n) begin
    if (!rst_n) {sync, meta} <= 2'b00;
    else        {sync, meta} <= {meta, src_level};
end
// use sync; meta feeds nothing else
```

Two flops per bit on a bus is the mistake worth naming. Each bit settles
independently, so a counter stepping `0111 -> 1000` can be sampled as `1111`.
The bus needs gray coding, a handshake, or a FIFO.

Three details that decide whether a structurally correct crossing actually
works: the source must be a registered output, because a combinational signal
glitches and the synchroniser captures the glitch faithfully; the first stage
must fan out only to the second, because two loads can resolve to different
values; and the SDC has to declare the domains asynchronous, or STA reports
meaningless violations across the boundary.

Every pattern with working code, plus what to randomise in simulation to make
CDC bugs reproducible, is in [references/cdc-patterns.md](references/cdc-patterns.md).

## Timing failures

Establish which constraint failed before proposing anything, because the fixes
have nothing in common:

- **Setup**: data arrives too late. Gets better with a slower clock.
- **Hold**: data arrives too early. A slower clock does nothing at all.

Then locate the cause in the report. Split the arrival time into clock network
delay and data path delay. Skew above roughly 10% of the period points at the
clock tree; a data path that is mostly logic points at the RTL; a path that
only fails after routing points at the floorplan.

Setup fixes, cheapest first: fix the single worst path and re-report, because
400 failing paths are usually 20 real problems; pipeline the deep logic;
restructure a priority chain into a mux or an adder chain into a tree; balance
logic across the register boundary; let the resizer upsize and buffer, which
buys tens of picoseconds rather than nanoseconds; and relax the clock only when
the frequency target was arbitrary rather than required.

A path failing by 10% is a logic problem. A path failing by 200% is an
architecture problem, and tool effort will not close it.

Hold is normally fixed by the tool inserting delay buffers. When violations
survive that, look for clock skew on the path, a flop-to-flop connection with
no logic across a hierarchy boundary, or a crossing that should never have been
timed — in which case fix the CDC rather than the hold.

Report reading, the delay-line walkthrough, SDC examples and the multicycle
path trap are in [references/timing-closure.md](references/timing-closure.md).

## Before trusting a clean report

A clean report and a correct design are different claims. Check which corner
was analysed, whether clocks were ideal or propagated, whether parasitics were
extracted or estimated, and how many endpoints were unconstrained. The worst
case is a `CLOCK_PORT` that names a port which does not exist: no clock gets
created, nothing is checked, and the report is clean because it is empty.

## Honest limits

`cdc_scan.py` infers domains from `always` block sensitivity lists within a
single module. It does not elaborate the design, so it does not follow signals
across module instantiations, through generate blocks, or into macros — a
crossing that happens at the top level between two instances will not be found.
It assumes a signal named like a reset in an edge-sensitive list is a reset.
Its synchroniser detection looks for a chain of flops whose right-hand side is
a bare identifier, so a synchroniser written with any logic in the path reads
as unsynchronised, which is the safe direction to be wrong in.

A clean scan means no structural problem was found in the files given. It does
not mean the protocol across the boundary is correct, that the FIFO depth is
adequate, or that the MTBF is acceptable. For a design going to silicon, a
dedicated CDC tool that elaborates the full hierarchy is still the authority.
