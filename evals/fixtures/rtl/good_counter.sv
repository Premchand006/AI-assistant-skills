// Fixture: clean RTL. The checker is expected to report nothing above info
// severity on this file.
`default_nettype none

module good_counter #(
    parameter int WIDTH = 8
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              en,
    output logic [WIDTH-1:0] count,
    output logic             wrapped
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count   <= '0;
            wrapped <= 1'b0;
        end else if (en) begin
            count   <= count + 1'b1;
            wrapped <= (count == {WIDTH{1'b1}});
        end else begin
            wrapped <= 1'b0;
        end
    end

endmodule

`default_nettype wire
