/*
    Copyright 2026 Ken Pettit

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

// LRAM_IHP16x8: 16 words x 8 bits of latches with one clocked write port
// and one asynchronous read port (the PRISM shard FIFO storage as a macro:
// eight bit rows, the sixteen words across, see placeram/ihp_lram_data.py).
//
// Write port (DFFRAM's latch byte, USE_LATCH=1): CLK is inverted once and
// feeds an integrated clock gate per word (lgcp).  The gate's enable is the
// decoded WE & WA, latched while the inverted clock is low - the high phase
// of CLK - so the decode may settle there without glitching the gated
// clock.  The gated clock then opens the word's eight latches for the LOW
// phase of the cycle in which WE / WA / Di are presented and closes them on
// the next rising edge.  WE, WA and Di therefore behave like the inputs of
// a synchronous RAM written at that rising edge (setup before the falling
// edge, hold through the rising edge) and the word is readable from the
// falling edge on; writes may follow each other every cycle.
//
// Read port: RA is predecoded (two 2-to-4 groups) and combined per word
// into a select; per bit an AND-OR tree (a22oi per word pair, and2 per
// quad, nand4 over the quads) drives Do, combinationally.
//
// RST_N clears every latch asynchronously (dlhrq).
//
// The module name is the macro LRAM_TOP so the west-pin variant
// (models/lram_ihp_left, LRAM_IHP_LEFT16x8: the same netlist, the rows
// mirrored and every pin on the W edge) reads this file under its own name.

`default_nettype none

`ifndef LRAM_TOP
`define LRAM_TOP LRAM_IHP16x8
`endif

// Predecoder: LO[i] = EN & (A[1:0] == i), HI[j] = (A[3:2] == j).
module PREDEC4_EN (
    input  wire       EN,
    input  wire [3:0] A,
    output wire [3:0] LO,
    output wire [3:0] HI
);
    wire [3:0] A_N;
    INV_1  INV0 (.Y(A_N[0]), .A(A[0]));
    INV_1  INV1 (.Y(A_N[1]), .A(A[1]));
    INV_1  INV2 (.Y(A_N[2]), .A(A[2]));
    INV_1  INV3 (.Y(A_N[3]), .A(A[3]));
    AND3_1 LO0  (.A(A_N[0]), .B(A_N[1]), .C(EN), .X(LO[0]));
    AND3_1 LO1  (.A(A[0]),   .B(A_N[1]), .C(EN), .X(LO[1]));
    AND3_1 LO2  (.A(A_N[0]), .B(A[1]),   .C(EN), .X(LO[2]));
    AND3_1 LO3  (.A(A[0]),   .B(A[1]),   .C(EN), .X(LO[3]));
    AND2_1 HI0  (.A(A_N[2]), .B(A_N[3]), .X(HI[0]));
    AND2_1 HI1  (.A(A[2]),   .B(A_N[3]), .X(HI[1]));
    AND2_1 HI2  (.A(A_N[2]), .B(A[3]),   .X(HI[2]));
    AND2_1 HI3  (.A(A[2]),   .B(A[3]),   .X(HI[3]));
endmodule

// Predecoder without an enable: LO[i] = (A[1:0] == i), HI[j] = (A[3:2] == j).
module PREDEC4 (
    input  wire [3:0] A,
    output wire [3:0] LO,
    output wire [3:0] HI
);
    wire [3:0] A_N;
    INV_1  INV0 (.Y(A_N[0]), .A(A[0]));
    INV_1  INV1 (.Y(A_N[1]), .A(A[1]));
    INV_1  INV2 (.Y(A_N[2]), .A(A[2]));
    INV_1  INV3 (.Y(A_N[3]), .A(A[3]));
    AND2_1 LO0  (.A(A_N[0]), .B(A_N[1]), .X(LO[0]));
    AND2_1 LO1  (.A(A[0]),   .B(A_N[1]), .X(LO[1]));
    AND2_1 LO2  (.A(A_N[0]), .B(A[1]),   .X(LO[2]));
    AND2_1 LO3  (.A(A[0]),   .B(A[1]),   .X(LO[3]));
    AND2_1 HI0  (.A(A_N[2]), .B(A_N[3]), .X(HI[0]));
    AND2_1 HI1  (.A(A[2]),   .B(A_N[3]), .X(HI[1]));
    AND2_1 HI2  (.A(A_N[2]), .B(A[3]),   .X(HI[2]));
    AND2_1 HI3  (.A(A[2]),   .B(A[3]),   .X(HI[3]));
endmodule

module `LRAM_TOP
#(
    parameter WSIZE = 1,                    // word width in bytes (the flow passes it; the placer lays out 1)
    parameter COUNT = 16
)
(
    input  wire               CLK,
    input  wire               RST_N,
    input  wire               WE,
    input  wire [3:0]         WA,
    input  wire [WSIZE*8-1:0] Di,
    input  wire [3:0]         RA,
    output wire [WSIZE*8-1:0] Do
);
    localparam W = WSIZE * 8;

    wire         clk_b;
    wire         rst_root;
    wire [3:0]   wlo, whi;                  // write predecode
    wire [3:0]   rlo, rhi;                  // read predecode
    wire [15:0]  gclk;                      // gated clock per word
    wire [15:0]  rsel;                      // read select per word
    wire [W-1:0] di_buf;
    wire [W-1:0] rst_row;
    wire [W-1:0] q [0:15];

    INV_4      CLKINV  (.Y(clk_b),    .A(CLK));
    CLKBUF_4   RSTROOT (.X(rst_root), .A(RST_N));
    PREDEC4_EN WDEC    (.EN(WE), .A(WA), .LO(wlo), .HI(whi));
    PREDEC4    RDEC    (.A(RA),          .LO(rlo), .HI(rhi));

    generate
        genvar w, b, p, k;

        for (w = 0; w < 16; w = w + 1) begin : WORD
            wire wsel;
            AND2_1 WSEL (.A(wlo[w % 4]), .B(whi[w / 4]), .X(wsel));
            LGCP_1 CG   (.CLK(clk_b), .GATE(wsel), .GCLK(gclk[w]));
            AND2_1 RSEL (.A(rlo[w % 4]), .B(rhi[w / 4]), .X(rsel[w]));
            for (b = 0; b < W; b = b + 1) begin : BIT
                DLHRQ_1 STORAGE (.D(di_buf[b]), .GATE(gclk[w]), .RESET_B(rst_row[b]), .Q(q[w][b]));
            end
        end

        for (b = 0; b < W; b = b + 1) begin : ROW
            wire [7:0] pair_n;                          // low when the pair holds the selected word's 1
            wire [3:0] quad_n;                          // low when the quad does
            wire       do_pre;
            CLKBUF_2 DIBUF  (.X(di_buf[b]),  .A(Di[b]));
            CLKBUF_2 RSTBUF (.X(rst_row[b]), .A(rst_root));
            for (p = 0; p < 8; p = p + 1) begin : PAIR
                A22OI_1 SEL (.A1(q[2*p][b]),   .A2(rsel[2*p]),
                             .B1(q[2*p+1][b]), .B2(rsel[2*p+1]),
                             .Y(pair_n[p]));
            end
            for (k = 0; k < 4; k = k + 1) begin : QUAD
                AND2_1 QAND (.A(pair_n[2*k]), .B(pair_n[2*k+1]), .X(quad_n[k]));
            end
            NAND4_1  ONAND (.A(quad_n[0]), .B(quad_n[1]), .C(quad_n[2]), .D(quad_n[3]), .Y(do_pre));
            CLKBUF_2 DOBUF (.X(Do[b]), .A(do_pre));
        end
    endgenerate
endmodule
