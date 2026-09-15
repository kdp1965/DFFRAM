// Behavioral, zero-delay models of the IHP sg13g2 standard cells used by the
// CFGMEM building blocks, for Verilator. The vendor models use UDP primitives
// that Verilator cannot compile. Functions follow the liberty file.
// The sg13cmos5l library is the same cells under another prefix; the Makefile
// derives its model file from this one.
`default_nettype none

module sg13g2_dlhq_1 (input wire D, input wire GATE, output reg Q);
    always_latch if (GATE) Q = D;   // transparent while GATE is high
endmodule

module sg13g2_a22oi_1 (input wire A1, input wire A2, input wire B1, input wire B2, output wire Y);
    assign Y = ~((A1 & A2) | (B1 & B2));
endmodule

module sg13g2_and2_1 (input wire A, input wire B, output wire X);  assign X = A & B; endmodule
module sg13g2_and2_2 (input wire A, input wire B, output wire X);  assign X = A & B; endmodule
module sg13g2_and3_1 (input wire A, input wire B, input wire C, output wire X);  assign X = A & B & C; endmodule
module sg13g2_and4_1 (input wire A, input wire B, input wire C, input wire D, output wire X);  assign X = A & B & C & D; endmodule
module sg13g2_nand4_1 (input wire A, input wire B, input wire C, input wire D, output wire Y);  assign Y = ~(A & B & C & D); endmodule
module sg13g2_nor2b_1 (input wire A, input wire B_N, output wire Y);  assign Y = ~(A | ~B_N); endmodule
module sg13g2_inv_1 (input wire A, output wire Y);  assign Y = ~A; endmodule
module sg13g2_buf_2 (input wire A, output wire X);  assign X = A; endmodule
module sg13g2_buf_4 (input wire A, output wire X);  assign X = A; endmodule
module sg13g2_buf_16 (input wire A, output wire X);  assign X = A; endmodule
module sg13g2_mux2_2 (input wire A0, input wire A1, input wire S, output wire X);  assign X = S ? A1 : A0; endmodule
module sg13g2_ebufn_4 (input wire A, input wire TE_B, output wire Z);  assign Z = TE_B ? 1'bz : A; endmodule
module sg13g2_tiehi (output wire L_HI);  assign L_HI = 1'b1; endmodule
module sg13g2_tielo (output wire L_LO);  assign L_LO = 1'b0; endmodule

// Antenna diode, fillers and decaps: no logic function.
module sg13g2_antennanp (input wire A); endmodule
module sg13g2_fill_1 (); endmodule
module sg13g2_fill_2 (); endmodule
module sg13g2_fill_4 (); endmodule
module sg13g2_fill_8 (); endmodule
module sg13g2_decap_4 (); endmodule
module sg13g2_decap_8 (); endmodule

// Cells used by the PRISM/TinyQV RTL when hardened on IHP libraries.
module sg13g2_or2_1 (input wire A, input wire B, output wire X);  assign X = A | B; endmodule
module sg13g2_or2_2 (input wire A, input wire B, output wire X);  assign X = A | B; endmodule
module sg13g2_dlygate4sd3_1 (input wire A, output wire X);  assign X = A; endmodule
// Integrated clock gate: enable is latched while CLK is low.
module sg13g2_lgcp_1 (input wire CLK, input wire GATE, output wire GCLK);
    reg en;
    always_latch if (!CLK) en = GATE;
    assign GCLK = CLK & en;
endmodule
