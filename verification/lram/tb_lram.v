// One LRAM_IHP16x8 latch RAM.  The module name comes in with -DLRAM=... so
// the same bench runs on the RTL model (block definitions + cell models)
// and on the gate-level netlist from products/.
`default_nettype none

module tb_lram (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       we,
    input  wire [3:0] wa,
    input  wire [7:0] di,
    input  wire [3:0] ra,
    output wire [7:0] dout
);
    `LRAM u (
        .CLK   (clk),
        .RST_N (rst_n),
        .WE    (we),
        .WA    (wa),
        .Di    (di),
        .RA    (ra),
        .Do    (dout)
    );
endmodule
