// Fixture: deliberately broken RTL used by tools/test_scripts.py.
// Every defect here is one the checker is expected to find.
module bad_fifo (
    input  wire        clk,
    input  wire        rst,
    input  wire        push,
    input  wire [7:0]  din,
    output reg  [7:0]  dout,
    output reg         full
);
    reg [7:0] mem [0:15];
    reg [3:0] wptr;
    reg [2:0] state;
    real      fill_ratio;          // unsynthesisable type

    initial wptr = 4'd0;           // initial block

    // blocking assignment in a clocked block, and a level-sensitive reset term
    always @(posedge clk or rst) begin
        if (rst)
            wptr = 4'd0;
        else if (push)
            wptr = wptr + 4'd1;
    end

    // wptr is driven from a second procedural block as well
    always @(posedge clk) begin
        if (push) wptr <= wptr + 4'd1;
    end

    // combinational case with no default: infers a latch on dout
    always @(*) begin
        case (state)
            3'd0: dout = mem[0];
            3'd1: dout = mem[1];
        endcase
    end

    // explicit sensitivity list that will drift
    always @(wptr) begin
        full = (wptr == 4'd15);
    end

    always @(posedge clk) begin
        #5 $display("wptr=%d", wptr);   // delay control + system task
    end
endmodule
