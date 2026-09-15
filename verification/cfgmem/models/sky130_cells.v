// Behavioral, zero-delay models of the sky130_fd_sc_hd cells referenced by the
// sky130 CFGMEM building blocks and netlists, for Verilator (the PDK models
// use UDP primitives). Functions follow the liberty file.
`default_nettype none

module sky130_fd_sc_hd__dlxtp_1 (input wire D, input wire GATE, output reg Q);
    always_latch if (GATE) Q = D;
endmodule

module sky130_fd_sc_hd__dfxtp_1 (input wire CLK, input wire D, output reg Q);
    always_ff @(posedge CLK) Q <= D;
endmodule

// Integrated clock gate: enable is latched while CLK is low.
module sky130_fd_sc_hd__dlclkp_1 (input wire CLK, input wire GATE, output wire GCLK);
    reg en;
    always_latch if (!CLK) en = GATE;
    assign GCLK = CLK & en;
endmodule

module sky130_fd_sc_hd__nor4b_2 (input wire A, input wire B, input wire C, input wire D_N, output wire Y);
    assign Y = ~A & ~B & ~C & D_N;
endmodule
module sky130_fd_sc_hd__and4bb_2 (input wire A_N, input wire B_N, input wire C, input wire D, output wire X);
    assign X = ~A_N & ~B_N & C & D;
endmodule
module sky130_fd_sc_hd__and4b_2 (input wire A_N, input wire B, input wire C, input wire D, output wire X);
    assign X = ~A_N & B & C & D;
endmodule
module sky130_fd_sc_hd__and4_2 (input wire A, input wire B, input wire C, input wire D, output wire X);
    assign X = A & B & C & D;
endmodule
module sky130_fd_sc_hd__and3_2 (input wire A, input wire B, input wire C, output wire X);
    assign X = A & B & C;
endmodule
module sky130_fd_sc_hd__and3b_2 (input wire A_N, input wire B, input wire C, output wire X);
    assign X = ~A_N & B & C;
endmodule
module sky130_fd_sc_hd__nor3b_2 (input wire A, input wire B, input wire C_N, output wire Y);
    assign Y = ~A & ~B & C_N;
endmodule
module sky130_fd_sc_hd__and2b_2 (input wire A_N, input wire B, output wire X);  assign X = ~A_N & B; endmodule
module sky130_fd_sc_hd__and2_2 (input wire A, input wire B, output wire X);  assign X = A & B; endmodule
module sky130_fd_sc_hd__and2_1 (input wire A, input wire B, output wire X);  assign X = A & B; endmodule
module sky130_fd_sc_hd__a222oi_1 (input wire A1, input wire A2, input wire B1, input wire B2, input wire C1, input wire C2, output wire Y);
    assign Y = ~((A1 & A2) | (B1 & B2) | (C1 & C2));
endmodule
module sky130_fd_sc_hd__a21boi_1 (input wire A1, input wire A2, input wire B1_N, output wire Y);
    assign Y = ~((A1 & A2) | ~B1_N);
endmodule
module sky130_fd_sc_hd__nand4_1 (input wire A, input wire B, input wire C, input wire D, output wire Y);
    assign Y = ~(A & B & C & D);
endmodule
module sky130_fd_sc_hd__mux2_1 (input wire A0, input wire A1, input wire S, output wire X);  assign X = S ? A1 : A0; endmodule
module sky130_fd_sc_hd__mux2_2 (input wire A0, input wire A1, input wire S, output wire X);  assign X = S ? A1 : A0; endmodule
module sky130_fd_sc_hd__mux4_1 (input wire A0, input wire A1, input wire A2, input wire A3, input wire S0, input wire S1, output wire X);
    assign X = S1 ? (S0 ? A3 : A2) : (S0 ? A1 : A0);
endmodule
module sky130_fd_sc_hd__conb_1 (output wire HI, output wire LO);
    assign HI = 1'b1;
    assign LO = 1'b0;
endmodule
module sky130_fd_sc_hd__ebufn_2 (input wire A, input wire TE_B, output wire Z);  assign Z = TE_B ? 1'bz : A; endmodule
module sky130_fd_sc_hd__ebufn_4 (input wire A, input wire TE_B, output wire Z);  assign Z = TE_B ? 1'bz : A; endmodule
module sky130_fd_sc_hd__clkbuf_2 (input wire A, output wire X);  assign X = A; endmodule
module sky130_fd_sc_hd__clkbuf_4 (input wire A, output wire X);  assign X = A; endmodule
module sky130_fd_sc_hd__clkbuf_16 (input wire A, output wire X);  assign X = A; endmodule
module sky130_fd_sc_hd__inv_1 (input wire A, output wire Y);  assign Y = ~A; endmodule
module sky130_fd_sc_hd__inv_4 (input wire A, output wire Y);  assign Y = ~A; endmodule

// Antenna diode, fillers, decaps and taps: no logic function.
module sky130_fd_sc_hd__diode_2 (input wire DIODE); endmodule
module sky130_fd_sc_hd__fill_1 (); endmodule
module sky130_fd_sc_hd__fill_2 (); endmodule
module sky130_fd_sc_hd__decap_3 (); endmodule
module sky130_fd_sc_hd__decap_4 (); endmodule
module sky130_fd_sc_hd__decap_6 (); endmodule
module sky130_fd_sc_hd__decap_8 (); endmodule
module sky130_fd_sc_hd__decap_12 (); endmodule
module sky130_fd_sc_hd__tapvpwrvgnd_1 (); endmodule
