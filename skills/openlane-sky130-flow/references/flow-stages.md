# The Classic flow, stage by stage

Loaded on demand. For each stage: what it does, how it fails, and what to
change when it does. Step names are the OpenLane 2 names that appear as run
subdirectory names (`05-yosys-synthesis`, `31-openroad-globalrouting`, ...).

The Classic flow in step order:

```
Verilator.Lint -> Checker.LintErrors -> Yosys.JsonHeader -> Yosys.Synthesis
-> Checker.YosysUnmappedCells -> OpenROAD.CheckSDCFiles -> OpenROAD.STAPrePNR
-> OpenROAD.Floorplan -> OpenROAD.TapEndcapInsertion -> OpenROAD.IOPlacement
-> OpenROAD.GeneratePDN -> OpenROAD.GlobalPlacement -> OpenROAD.RepairDesign
-> OpenROAD.DetailedPlacement -> OpenROAD.CTS -> OpenROAD.ResizerTimingPostCTS
-> OpenROAD.GlobalRouting -> OpenROAD.DetailedRouting -> OpenROAD.FillInsertion
-> OpenROAD.RCX -> OpenROAD.STAPostPNR -> Magic.StreamOut -> Magic.DRC
-> Magic.SpiceExtraction -> Netgen.LVS -> Checker.*
```

You can run a subset with `--from` and `--to`, which is how you iterate without
re-running synthesis every time:

```bash
python3 -m openlane --last-run --from OpenROAD.GlobalPlacement config.json
```

## Lint and synthesis

`Verilator.Lint` runs before anything else, so a lint error stops the run in
seconds. That is the cheapest failure available; take it.

`Yosys.Synthesis` maps RTL to standard cells.

| Symptom | Cause | Fix |
|---|---|---|
| `Checker.YosysUnmappedCells` fails | a cell Yosys could not map, usually an inferred multiplier, DSP or memory | instantiate a macro, or rewrite the operator; sky130 has no DSP blocks |
| "Latch inferred" | incomplete combinational assignment | fix the RTL; a latch will not time |
| Cell count far above expectation | a `/` or `%` synthesised into a divider, or a large `for` loop unrolled | check the RTL with the `rtl-verilog-lint` skill |
| Blackbox warnings | a module in the hierarchy has no definition | add the file to `VERILOG_FILES` |

`SYNTH_STRATEGY` trades area against delay: `"AREA 0"` through `"AREA 3"` and
`"DELAY 0"` through `"DELAY 4"`. Change it only after the design closes once;
strategy shopping before that hides the real problem.

## Static timing, before place and route

`OpenROAD.STAPrePNR` runs with ideal clocks and estimated wire loads. It is
optimistic by construction. Treat a pre-PNR failure as fatal: if the design
does not meet timing on ideal clocks it will not meet timing after routing.

Timing constraints come from your SDC. OpenLane generates a default one from
`CLOCK_PORT` and `CLOCK_PERIOD`; a real design usually needs its own:

```json
"PNR_SDC_FILE": "dir::constraints.sdc",
"SIGNOFF_SDC_FILE": "dir::constraints.sdc"
```

If `CLOCK_PORT` names a port that does not exist, STA runs with no clock, every
path passes, and the failure surfaces much later. `scripts/check_config.py`
checks this against your RTL for exactly this reason.

## Floorplan and power

`FP_CORE_UTIL` sets the target core utilisation. `FP_SIZING` decides whether
the die comes from utilisation (`"relative"`, the default) or from `DIE_AREA`
(`"absolute"`). Setting `DIE_AREA` without `FP_SIZING: "absolute"` silently has
no effect.

`OpenROAD.GeneratePDN` builds the power grid. Failures here usually mean the
grid pitch does not fit the die:

| Symptom | Fix |
|---|---|
| "no power straps" / unconnected power | check `FP_PDN_VPITCH`, `FP_PDN_HPITCH` against die size |
| Macro power pins unconnected | set `PDN_MACRO_CONNECTIONS` for each macro instance |
| Tap cell errors | `FP_TAP_HORIZONTAL_HALFDISTANCE` must match the PDK rule |

## Placement

`OpenROAD.GlobalPlacement` fails when the design cannot fit at the requested
utilisation. Lower `FP_CORE_UTIL` by 5 and retry rather than adjusting many
variables at once.

`PL_TARGET_DENSITY_PCT` controls how tightly the placer packs cells; it needs
headroom above `FP_CORE_UTIL`, and the flow default is derived from it. Raising
utilisation and target density together is the usual cause of a router that
never converges.

## Clock tree synthesis

`OpenROAD.CTS` replaces the ideal clock with a real buffer tree, which is where
most designs first fail timing. Hold violations appearing only after CTS are
normal; `OpenROAD.ResizerTimingPostCTS` inserts delay buffers to fix them.

If hold violations survive the resizer, the usual causes are a clock tree that
is too skewed (check `clock__skew__worst`) or a reset that is asynchronous on
one end and synchronous on the other.

## Routing

`OpenROAD.GlobalRouting` estimates congestion; `OpenROAD.DetailedRouting`
(TritonRoute) does the real work and reports DRC violations as
`route__drc_errors`.

| Symptom | Fix |
|---|---|
| Congestion in global routing | lower `FP_CORE_UTIL`; raise `GRT_ADJUSTMENT` only as a second resort |
| Detailed routing never converges | reduce utilisation; check for a macro blocking a routing channel |
| Antenna violations | enable diode insertion (`RUN_ANTENNA_REPAIR`), or let `GRT_REPAIR_ANTENNAS` place them |
| Violations only on one layer | check `RT_MAX_LAYER`; sky130 designs usually stop at met4 or met5 |

A handful of DRC violations after detailed routing is not a "nearly clean" run.
Sign-off is zero.

## Sign-off

`Magic.DRC` and `Netgen.LVS` are the two that decide whether a tapeout accepts
the design. LVS mismatches usually come from power connections that exist in
the layout but not in the netlist, or from a macro whose LEF and GDS disagree.

`OpenROAD.RCX` extracts parasitics into SPEF, and `OpenROAD.STAPostPNR` is the
timing number that counts. Compare it against the pre-PNR number: a large drop
means the wire load model was wrong, usually because the floorplan is too
spread out.

## Metrics worth reading

Every step writes metrics; the ones that decide whether a run is usable:

| Metric | Meaning | Acceptable |
|---|---|---|
| `timing__setup__ws` | worst setup slack, ns | >= 0 |
| `timing__hold__ws` | worst hold slack, ns | >= 0 |
| `route__drc_errors` | detailed routing violations | 0 |
| `magic__drc_error__count` | layout DRC | 0 |
| `design__lvs_error__count` | layout vs schematic | 0 |
| `antenna__violating__nets` | antenna rule | 0 |
| `design__instance__utilization` | achieved utilisation | below your target |

`scripts/summarize_run.py` pulls these out of a run directory and flags the
ones that are out of bounds.

## Iterating without burning hours

* Fix lint and synthesis problems before starting a full run.
* Use `--to OpenROAD.Floorplan` to check the floorplan alone.
* Use `--last-run --from <step>` to resume after a config change that only
  affects later steps. Changing a synthesis variable invalidates everything
  downstream, so resume from `Yosys.Synthesis` in that case.
* Keep one config change per run. Two changes and a different result tells you
  nothing about which one mattered.
