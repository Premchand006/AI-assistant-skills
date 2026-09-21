# UVM, and when it is the wrong answer

Loaded on demand.

## Choosing the stack

| Situation | Use |
|---|---|
| One module, a handful of directed cases | plain SystemVerilog with an error counter |
| A module with a protocol interface, open-source tools only | cocotb, or SystemVerilog with assertions |
| A reusable IP with a standard bus, many tests, a team | UVM |
| A chip-level integration test | UVM, or a directed C test on the embedded core |

UVM costs roughly a thousand lines of infrastructure before the first check
runs. That buys constrained random, factory overrides, sequence reuse across
blocks, and a structure other verification engineers recognise. For a FIFO it
is a bad trade. For an AXI slave that three teams will instantiate, it is the
cheapest option available.

It also needs a simulator with full UVM support. Verilator does not run UVM;
Icarus does not either. If the project is open-source-tools-only, cocotb with a
scoreboard and constrained random gives most of the value.

## Agent structure

```
env
├── agent (per interface)
│   ├── sequencer   - hands sequence items to the driver
│   ├── driver      - turns items into pin wiggles
│   └── monitor     - turns pin wiggles back into items, always present
├── scoreboard      - compares monitored items against a reference
└── coverage collector
```

The rule that keeps an agent reusable: the monitor observes, it never drives,
and it exists whether the agent is active or passive. A passive agent (monitor
only) is how you reuse a block-level agent at chip level, where something else
is driving the interface.

## Phases, and the two that cause the trouble

`build_phase` constructs components top-down, `connect_phase` wires them
bottom-up, `run_phase` is the only one that consumes simulation time.

```systemverilog
class my_test extends uvm_test;
    `uvm_component_utils(my_test)

    function void build_phase(uvm_phase phase);
        super.build_phase(phase);          // omitting this breaks the factory
        env = my_env::type_id::create("env", this);
    endfunction

    task run_phase(uvm_phase phase);
        my_seq seq = my_seq::type_id::create("seq");
        phase.raise_objection(this);        // without this the test ends at once
        seq.start(env.agent.sequencer);
        phase.drop_objection(this);
    endtask
endclass
```

The two failures that account for most "my UVM test does nothing" reports:

- **No objection raised.** `run_phase` returns immediately, the test ends
  before any stimulus, and UVM reports success.
- **`super.build_phase` omitted**, or `new` used instead of
  `type_id::create`. Both bypass the factory, so overrides silently do nothing
  and the component you meant to replace is still there.

## Sequences and constraints

```systemverilog
class burst_seq extends uvm_sequence #(bus_item);
    `uvm_object_utils(burst_seq)
    rand int unsigned len;
    constraint c_len { len inside {[4:16]}; }

    task body();
        repeat (len) begin
            bus_item item = bus_item::type_id::create("item");
            start_item(item);
            if (!item.randomize() with { addr % 4 == 0; })
                `uvm_error("RAND", "randomisation failed")
            finish_item(item);
        end
    endtask
endclass
```

Check the return value of `randomize()`. An over-constrained item fails
randomisation, and the default is to carry on with stale values, which produces
a test that runs and proves nothing.

## Reporting and exit status

UVM's report server decides the final status, and a run with zero errors and
zero checks passes. Two things to set explicitly:

```systemverilog
// Fail the run if a check never happened at all.
function void check_phase(uvm_phase phase);
    if (scoreboard.compares == 0)
        `uvm_error("SCOREBOARD", "no transactions were compared")
endfunction

// Make the simulator exit non-zero on UVM_ERROR.
set_report_severity_action_hier(UVM_ERROR, UVM_DISPLAY | UVM_COUNT);
set_report_max_quit_count(1);
```

## Assertions belong in the interface

```systemverilog
interface bus_if(input logic clk, input logic rst_n);
    logic        valid, ready;
    logic [31:0] data;

    clocking cb @(posedge clk);
        default input #1step output #1ns;   // sample before, drive after
        output valid, data;
        input  ready;
    endclocking

    property p_data_stable;
        @(posedge clk) disable iff (!rst_n)
        (valid && !ready) |=> $stable(data);
    endproperty
    a_data_stable: assert property (p_data_stable);
endinterface
```

The clocking block is what removes the drive-on-the-active-edge race for the
whole testbench at once: inputs sample before the edge, outputs drive after it.

Assertions in the interface run in every test that uses the interface, at
block level and at chip level, without anyone remembering to instantiate a
checker.

## Reviewing a UVM testbench

- Does every objection that is raised get dropped on every path, including
  error paths?
- Does the monitor exist in passive agents, and does it avoid driving?
- Is `randomize()`'s return value checked everywhere?
- Does `check_phase` fail when no transaction was compared?
- Are the constraints reachable? An over-constrained random test degrades into
  a directed test that looks random.
- Is the seed logged, and does the regression use more than one seed?
