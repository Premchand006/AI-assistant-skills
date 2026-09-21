---
name: openlane-sky130-flow
description: Drive an open-source RTL-to-GDSII run with OpenLane 2, OpenROAD, Yosys, Magic and Netgen on the Sky130 or GF180MCU PDK. Covers writing and validating config.json, choosing floorplan and utilisation values, resuming a run from a step, and reading the run directory when a step fails on congestion, antenna, DRC, LVS or timing. Use when the user mentions OpenLane, OpenROAD, Sky130, sky130A, GF180, Magic DRC, Netgen LVS, Efabless or a tapeout, when a config.json for a chip flow needs writing or fixing, or when a run has failed and its logs and metrics need interpreting. Not for writing the RTL itself, which belongs to rtl-verilog-lint.
license: MIT
version: 0.1.0
---

# OpenLane 2 on Sky130

A full run takes minutes to hours and most failed runs die in the first minute
on something a file check would have caught. So: validate the config, run with
a narrow scope, read the metrics, change one thing at a time.

## Before starting a run

```bash
python3 scripts/check_config.py config.json --pdk-root ~/.volare
```

This checks the things that cost a whole run when wrong: paths that do not
resolve, a `CLOCK_PORT` that is not a port of the RTL, a PDK family name where
a variant is needed, a utilisation the router will not survive, and `DIE_AREA`
set without `FP_SIZING: "absolute"`, which silently does nothing.

A minimum viable config, with the parts that matter:

```json
{
  "meta": { "version": 2 },
  "DESIGN_NAME": "my_design",
  "VERILOG_FILES": ["dir::src/my_design.v"],
  "CLOCK_PORT": "clk",
  "CLOCK_PERIOD": 20,
  "PDK": "sky130A",
  "FP_CORE_UTIL": 40
}
```

Three details that account for a large share of first-run failures:

- `dir::` resolves paths against the config file. A bare relative path resolves
  against the working directory, so the run breaks the first time someone
  starts it from somewhere else.
- `PDK` takes a variant (`sky130A`), not a family (`sky130`).
- `CLOCK_PORT` has to be a real port of the top module. If it is not, static
  timing runs with no clock, every path passes, and you find out at sign-off.

A fuller starting config with the reasoning inline is in
[references/config-template.json](references/config-template.json).

## Running

```bash
python3 -m pip install --upgrade openlane
python3 -m openlane --pdk-root ~/.volare config.json        # full flow
python3 -m openlane --to OpenROAD.Floorplan config.json     # stop early
python3 -m openlane --last-run --from OpenROAD.CTS config.json  # resume
python3 -m openlane --dockerized config.json                # pinned toolchain
```

`--dockerized` is the answer when a tool version is in question; the local
install picks up whatever Yosys and OpenROAD happen to be on the machine.

Each step writes into its own numbered directory (`05-yosys-synthesis`,
`31-openroad-globalrouting`), so the step that failed names itself.

## After a run

```bash
python3 scripts/summarize_run.py runs/          # newest run
python3 scripts/summarize_run.py runs/RUN_2026-09-21_10-00-00 --json
```

It reports where the run stopped, the tail of `error.log`, and the sign-off
metrics with the out-of-bounds ones flagged. The metrics that decide whether a
run is usable:

| Metric | Acceptable |
|---|---|
| `timing__setup__ws`, `timing__hold__ws` | >= 0 |
| `route__drc_errors` | 0 |
| `magic__drc_error__count` | 0 |
| `design__lvs_error__count` | 0 |
| `antenna__violating__nets` | 0 |

Sign-off is zero violations. A run with "only a few" DRC errors has not closed.

## Reading a failure

Start from the failing step's own directory, not from `error.log`. The flow
log carries what the flow surfaced; the tool log in the step directory carries
the cause.

| Failing step | Usual cause | First thing to try |
|---|---|---|
| `Checker.LintErrors` | RTL problem | fix the RTL; `rtl-verilog-lint` covers this |
| `Checker.YosysUnmappedCells` | inferred multiplier or memory | instantiate a macro; sky130 has no DSP blocks |
| `OpenROAD.STAPrePNR` fails | design does not meet timing on ideal clocks | fix the architecture, not the config; it will not get better after routing |
| `OpenROAD.GeneratePDN` | grid pitch does not fit the die | check `FP_PDN_VPITCH`/`FP_PDN_HPITCH` |
| `OpenROAD.GlobalPlacement` | design does not fit | drop `FP_CORE_UTIL` by 5 |
| `OpenROAD.DetailedRouting` | congestion | drop utilisation; `GRT_ADJUSTMENT` is a second resort |
| `Magic.DRC` | layout rule violation | read the Magic report; it names the rule |
| `Netgen.LVS` | netlist and layout disagree | usually power connections or a macro LEF/GDS mismatch |

Stage-by-stage detail, the full step list, and the variables that matter at
each stage are in [references/flow-stages.md](references/flow-stages.md).

## Working method

Change one variable per run. Two changes and a different outcome tells you
nothing about which one mattered, and each experiment costs real time.

When a change only affects later steps, resume with `--last-run --from <step>`
instead of re-running synthesis. Changing a synthesis variable invalidates
everything downstream, so resume from `Yosys.Synthesis` in that case.

When utilisation is the problem, lower it. Raising `GRT_ADJUSTMENT`,
`PL_TARGET_DENSITY_PCT` and routing layers to force a congested design through
produces a run that completes and a design that fails sign-off.

## Honest limits

`check_config.py` reads the config and the RTL as text. It does not elaborate
the design, so it cannot tell you whether the top module is the one you meant,
and its port extraction is regex-based and can miss ports declared through
macros or `include` files. It does not validate PDK-specific variable names
beyond the common ones.

`summarize_run.py` reads the metrics files the run wrote. If a step crashed
before writing metrics, there is nothing to summarise and it says so rather
than guessing.

Neither script is sign-off. Magic DRC, Netgen LVS and post-PNR STA are the
authorities, and a shuttle programme will run its own checks on top.
