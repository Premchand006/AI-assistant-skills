// Fixture: a testbench that cannot fail. Prints everything, checks nothing,
// has no timeout, and exits 0 no matter what the DUT does.
`timescale 1ns/1ps

module weak_tb;
    logic clk = 0;
    logic [7:0] din, dout;

    always #5 clk = ~clk;

    dut u_dut (.clk(clk), .din(din), .dout(dout));

    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, weak_tb);

        @(posedge clk) din = 8'h00;
        @(posedge clk) din = 8'h01;
        @(posedge clk) din = 8'hFF;

        repeat (10) @(posedge clk);
        $display("dout = %h", dout);
        $display("done");
        $finish;
    end
endmodule
