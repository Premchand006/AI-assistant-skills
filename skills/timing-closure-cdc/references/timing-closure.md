# Reading STA reports and closing timing

Loaded on demand.

## The two constraints

**Setup**: data has to arrive before the capture edge.
`slack = required - arrival = (T_clk - T_setup - skew) - (T_clk2q + T_logic + T_wire)`.
Setup failures get better when you slow the clock down.

**Hold**: data must not arrive too early, before the capture flop has latched
the previous value. `slack = (T_clk2q + T_logic + T_wire) - (T_hold + skew)`.
Hold failures do not care about clock period at all — slowing the clock does
nothing. That is the fastest way to tell the two apart when reading a report.

| Symptom | What it means |
|---|---|
| Setup fails, hold passes | logic is too deep for the period |
| Hold fails, setup passes | a path is too short, usually clock skew or a direct flop-to-flop connection |
| Both fail on one path | the clock tree is badly skewed on that path |
| Fails only post-CTS | the ideal clock was hiding it; this is normal and expected |
| Fails only post-route | wire delay; the floorplan is too spread out |

## Reading an OpenSTA / OpenROAD report

```
Startpoint: u_ctrl/state_reg[2] (rising edge-triggered flip-flop clocked by clk)
Endpoint:   u_dp/acc_reg[15]    (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type:  max                       <- max = setup, min = hold

  Delay    Time   Description
  -----------------------------------
   0.00    0.00   clock clk (rise edge)
   0.21    0.21   clock network delay      <- launch clock path
   0.00    0.21 ^ state_reg[2]/CLK
   0.34    0.55 v state_reg[2]/Q           <- clk-to-q
   1.87    2.42   data path                <- combinational logic: the part you own
  -----------------------------------
                  data arrival time  2.42

  10.00   10.00   clock clk (rise edge)
   0.19   10.19   clock network delay      <- capture clock path
  -0.08   10.11   clock uncertainty
  -0.12    9.99   library setup time
  -----------------------------------
                  data required time  9.99
                  slack (MET)         7.57
```

Read it in this order: is it max or min, how much of the arrival time is the
data path versus the clock network, and is the skew between launch and capture
clock network delay large. A skew above roughly 10% of the period points at
the clock tree, not at your logic.

## Fixing setup

In the order that costs least:

1. **Look at the whole path first.** A report of 400 failing paths is usually
   20 real problems; fix the worst path and see what disappears.
2. **Pipeline the deep logic.** Insert a register stage and change the
   protocol to match. This is the real fix for a path that is simply too long.
3. **Restructure the logic.** A priority chain (`if/else if/else if`) is as
   deep as it is long; a `case` over mutually exclusive conditions is a mux.
   An adder tree beats a chain of adders.
4. **Move logic across the register boundary** so both sides are balanced,
   rather than one side empty and one side full.
5. **Retime, upsize, or let the tool resize.** `OpenROAD.RepairDesign` and the
   post-CTS resizer will upsize drivers and insert buffers. This buys tens of
   picoseconds, not nanoseconds.
6. **Relax the clock.** Legitimate when the frequency target was arbitrary,
   dishonest when it was a requirement.

A path that fails by 10% is a logic-restructuring problem. A path that fails by
200% is an architecture problem, and no amount of tool effort fixes it.

## Fixing hold

Hold is usually fixed automatically by inserting delay buffers, and the tool is
better at it than you are. When hold violations survive the resizer, look for:

- Large clock skew on that path: the capture flop's clock arrives much earlier
  than the launch flop's.
- A direct flop-to-flop connection with no logic between them, particularly
  across a hierarchy boundary.
- A crossing with no synchroniser, where the tool is timing a path that should
  not have been timed at all. Fix the CDC, not the hold.

Fixing hold by slowing the clock does not work, which is worth saying out loud
whenever someone suggests it.

## Constraints that change the numbers

```tcl
create_clock -name clk -period 10.0 [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]        # jitter + margin
set_input_delay  -clock clk 2.0 [remove_from_collection [all_inputs] [get_ports clk]]
set_output_delay -clock clk 2.0 [all_outputs]

# A path that genuinely has more than one cycle to complete
set_multicycle_path -setup 2 -from [get_pins mult/*/Q] -to [get_pins acc_reg/D]
set_multicycle_path -hold  1 -from [get_pins mult/*/Q] -to [get_pins acc_reg/D]
```

Two constraint mistakes account for most "the design closed and the chip does
not work" stories:

- **A multicycle path declared without the matching hold exception.** The
  `-setup 2` alone moves the hold check to the wrong edge.
- **Missing input and output delays.** Without them the tool assumes the I/O
  timing is free, the interior closes easily, and the interface fails.

And the one that produces the opposite outcome: a `CLOCK_PORT` naming a port
that does not exist means no clock is created at all, every path is
unconstrained, and the report is clean because nothing was checked. Look for
"no clock" or "unconstrained" warnings before trusting a clean report.

## Before believing a timing report

- Which corner? Slow-slow for setup, fast-fast for hold. A single-corner clean
  result is half an answer.
- Ideal or propagated clocks? Pre-CTS numbers are optimistic by construction.
- Wire load estimates or extracted parasitics? Pre-route timing routinely
  improves by 20% or degrades by 50% after extraction.
- How many paths were analysed? Zero unconstrained endpoints is the number to
  check; a report with unconstrained endpoints is not a sign-off report.
