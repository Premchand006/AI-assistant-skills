// Fixture: three crossings, one of each kind the scanner should distinguish.
`default_nettype none

module cdc_mixed (
    input  wire        clk_fast,
    input  wire        clk_slow,
    input  wire        rst_n,
    input  wire        req_in,
    input  wire [7:0]  data_in,
    output logic       ack_out,
    output logic [7:0] data_out,
    output logic       flag_out
);

    logic       req_fast;
    logic [7:0] data_fast;
    logic       flag_fast;

    // --- fast domain: sources -------------------------------------------
    always_ff @(posedge clk_fast or negedge rst_n) begin
        if (!rst_n) begin
            req_fast  <= 1'b0;
            data_fast <= '0;
            flag_fast <= 1'b0;
        end else begin
            req_fast  <= req_in;
            data_fast <= data_in;
            flag_fast <= ~flag_fast;
        end
    end

    // --- slow domain ------------------------------------------------------
    logic req_meta, req_sync;
    logic [7:0] data_meta, data_sync;

    always_ff @(posedge clk_slow or negedge rst_n) begin
        if (!rst_n) begin
            req_meta  <= 1'b0;
            req_sync  <= 1'b0;
            data_meta <= '0;
            data_sync <= '0;
            ack_out   <= 1'b0;
            data_out  <= '0;
            flag_out  <= 1'b0;
        end else begin
            // correct: two-flop synchroniser on a single-bit signal
            req_meta <= req_fast;
            req_sync <= req_meta;
            ack_out  <= req_sync;

            // wrong: multi-bit bus through a two-flop synchroniser
            data_meta <= data_fast;
            data_sync <= data_meta;
            data_out  <= data_sync;

            // wrong: no synchroniser at all
            flag_out <= flag_fast;
        end
    end

endmodule

`default_nettype wire
