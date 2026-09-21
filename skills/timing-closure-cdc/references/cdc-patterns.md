# Clock-domain crossing patterns

Loaded on demand. One pattern per kind of signal. Picking the wrong pattern is
the most common CDC bug after using none at all.

| What crosses | Pattern |
|---|---|
| Single-bit level (status, enable) | two-flop synchroniser |
| Single-bit pulse | toggle synchroniser, or pulse stretcher if source is faster |
| Multi-bit, changes one bit at a time | gray-coded two-flop synchroniser |
| Multi-bit data, arbitrary values | handshake with data held stable, or an async FIFO |
| Streaming data | async FIFO with gray-coded pointers |
| Reset | async assert, synchronous de-assert, one per domain |

## Two-flop synchroniser

```systemverilog
logic meta, sync;
always_ff @(posedge clk_dst or negedge rst_n) begin
    if (!rst_n) {sync, meta} <= 2'b00;
    else        {sync, meta} <= {meta, src_signal};
end
// use `sync`, never `meta`
```

Why two flops: the first one may go metastable when `src_signal` changes near
the edge. The second gives it most of a clock period to settle. Three stages
are used when the clock is very fast or the MTBF budget is tight.

Two conditions that are easy to miss:

- `src_signal` has to be a registered output in the source domain. A
  combinational signal can glitch, and the synchroniser will faithfully
  capture the glitch.
- `meta` must not feed anything except `sync`. Fanning `meta` out to two places
  lets them resolve to different values, which is how a one-bit crossing
  produces an inconsistent state.

## Pulse across domains (toggle synchroniser)

A pulse one cycle wide in a fast domain can be missed entirely by a slower
domain. Convert it to a level change:

```systemverilog
// source domain: toggle on each pulse
always_ff @(posedge clk_src or negedge rst_n)
    if (!rst_n)       toggle <= 1'b0;
    else if (pulse_in) toggle <= ~toggle;

// destination domain: synchronise, then detect the edge
always_ff @(posedge clk_dst or negedge rst_n)
    if (!rst_n) {t3, t2, t1} <= 3'b000;
    else        {t3, t2, t1} <= {t2, t1, toggle};

assign pulse_out = t3 ^ t2;
```

This carries one pulse per destination clock period at most. If pulses can
arrive faster than the destination clock, you need a FIFO, not a toggle.

## Multi-bit: why two flops per bit is wrong

Each bit settles independently, so during the transition the destination can
sample a combination that never existed in the source. A counter going from
`0111` to `1000` can be read as `1111` or `0000`.

Two ways out:

**Gray code** works when exactly one bit changes per step, which is true for a
counter incrementing by one and false for anything else:

```systemverilog
assign gray = (bin >> 1) ^ bin;          // binary to gray
// destination: synchronise gray, then convert back
always_comb begin
    bin_dst[N-1] = gray_sync[N-1];
    for (int i = N-2; i >= 0; i--) bin_dst[i] = bin_dst[i+1] ^ gray_sync[i];
end
```

**Handshake** works for arbitrary values. The source holds the data stable
while `req` is asserted, and does not change it until `ack` comes back:

```
src: data <= value; req <= 1;
     wait for ack_sync;              // ack synchronised into src domain
     req <= 0;
dst: wait for req_sync;              // req synchronised into dst domain
     captured <= data;               // data is stable, no synchroniser needed
     ack <= 1;
```

The data bus itself crosses without a synchroniser, which is the point: it is
guaranteed stable by the protocol. Static CDC tools need to be told this, or
they will flag the bus.

## Async FIFO

For continuous data. The pointers are gray-coded and synchronised across the
boundary; the memory is dual-port and does not cross at all. Write it once,
verify it hard, then reuse it. The parts that go wrong:

- Full and empty must be computed in their own domains, from the local pointer
  and the synchronised remote pointer. Computing both in one domain is a bug.
- Full and empty are conservative by construction: full may assert one entry
  early and empty one entry late, because the synchronised pointer is stale.
  That is correct behaviour, not a bug to optimise away.
- Depth has to cover the synchroniser latency plus the burst size.

## Reset

An asynchronous reset asserted anywhere is fine. Releasing it is the problem:
if the release lands near a clock edge, some flops leave reset a cycle after
others, and a state machine can start in an illegal state.

```systemverilog
// one of these per clock domain
logic rst_meta, rst_sync_n;
always_ff @(posedge clk or negedge rst_async_n) begin
    if (!rst_async_n) {rst_sync_n, rst_meta} <= 2'b00;
    else              {rst_sync_n, rst_meta} <= {rst_meta, 1'b1};
end
```

Assert is asynchronous (immediate, no clock needed), de-assert is synchronous
to the local clock. Use `rst_sync_n` as the reset for that domain.

## Constraining crossings in the SDC

Static timing analysis will try to time paths between domains and report huge
violations that mean nothing. Tell it not to:

```tcl
# The two domains have no phase relationship at all.
set_clock_groups -asynchronous \
    -group [get_clocks clk_fast] -group [get_clocks clk_slow]

# On the synchroniser input, bound the delay instead of ignoring it, so the
# first stage cannot be starved by a long wire.
set_max_delay -from [get_pins src_reg/Q] -to [get_pins meta_reg/D] 5.0 -datapath_only
```

`set_false_path` on the crossing is common but blunt: it removes the path from
analysis entirely, including the wire delay into the first synchroniser flop.
`set_max_delay -datapath_only` keeps that bounded.

## What to verify, not just check structurally

Structure is necessary and not sufficient. In simulation:

- Randomise the phase relationship between the two clocks across runs. A CDC
  bug that only appears at one phase offset will not appear in a testbench
  with a fixed offset.
- Inject metastability: some simulators can randomly delay the synchroniser
  output by a cycle. Without that, RTL simulation will never show the failure.
- Run the protocol at both extremes of the clock ratio, not just the nominal.
