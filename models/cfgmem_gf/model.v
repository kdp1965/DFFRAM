/*
    Copyright 2026 Ken Pettit

    This file is part of the DFFRAM Memory Compiler.
    See https://github.com/Cloud-V/DFFRAM for further info.

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

// 8 x 44 Config MEM for the GF180 7-track library (gf180mcu_fd_sc_mcu7t5v0):
// the PRISM State Information Table of the ttboat26 TinyQV tile as a hard
// macro.  Same architecture as models/cfgmem_ihp: an 8-deep shift chain of
// latch words (row k loads from row k-1 and row 0 from Di0 while
// WROW[k] & WE0 is high), and a one-hot 8:1 read-out per bit, built here from
// four aoi22_1 (two words each, an active-low hit) merged by a nand4_1.  No
// bypass mux: the tile has a single macro, nothing is chained behind it.
// EN0 gates the decoder (the tile ties it high).
`default_nettype none

module CFGMEM8x44
#(
    parameter WSIZE = 44,
    parameter COUNT = 8
 )
(
    input   wire                 WE0,
    input   wire [7:0]           WROW,
    input   wire                 EN0,
    input   wire [2:0]           A0,
    input   wire [WSIZE-1:0]     Di0,
    output  wire [WSIZE-1:0]     Do0
);
    wire [7:0]           SEL1;
    wire [7:0]           SEL1_BUF;
    wire [7:0]           LE0;

    wire [WSIZE-1:0]     Di0_in[7:0];
    wire [WSIZE-1:0]     Do0_pre[7:0];
    wire [WSIZE-1:0]     Do1_pre[3:0];    // active-low hit of word pair p (words 2p, 2p+1)

    genvar i, q;

`ifndef NO_DIODES
    (* keep = "true" *)
    DIODE    DIODE_A0 [2:0]    (.DIODE(A0[2:0]));
    (* keep = "true" *)
    DIODE    DIODE_EN0         (.DIODE(EN0));
    (* keep = "true" *)
    DIODE    DIODE_WE0         (.DIODE(WE0));
`endif

    // DEC3x8 buffers its address and enable inputs itself (ABUF, ENBUF).
    DEC3x8 DEC0 (.EN(EN0), .A(A0), .SEL(SEL1));

    // Chain the 8 words: word i is loaded from the output of word i-1.
    assign Di0_in[0] = Di0;
    generate
        for (i = 1; i < 8; i = i + 1) begin : IN_MAP
            assign Di0_in[i] = Do0_pre[i-1];
        end

        // 8 word rows, each with a read-select buffer, protection diode and
        // the AND that forms the row load enable from WROW & WE0.
        for (i = 0; i < 8; i = i + 1) begin : SLICE
            CFG_WORD #(.WSIZE(WSIZE)) CWORD (.LE0(LE0[i]), .Di0(Di0_in[i]), .Do0(Do0_pre[i]));
            CLKBUF_8 SELBUF     (.X(SEL1_BUF[i]), .A(SEL1[i]));
            (* keep = "true" *)
            DIODE    DIODE_SEL1 (.DIODE(SEL1_BUF[i]));
            AND2_4   ROW_AND    (.X(LE0[i]), .A(WROW[i]), .B(WE0));
        end
    endgenerate

    // Read-out: per group of four words (a quad) two aoi22 per bit, each the
    // active-low hit of a word pair; the quad's row sits after its four words.
    generate
        for (q = 0; q < 2; q = q + 1) begin : QUADS
            for (i = 0; i < WSIZE; i = i + 1) begin : QBIT
                AOI22_1 QUAD_AOI0 (
                      .A1 (Do0_pre[q*4 + 0][i]),
                      .A2 (SEL1_BUF[q*4 + 0]),
                      .B1 (Do0_pre[q*4 + 1][i]),
                      .B2 (SEL1_BUF[q*4 + 1]),
                      .Y  (Do1_pre[q*2 + 0][i])
                );
                AOI22_1 QUAD_AOI1 (
                      .A1 (Do0_pre[q*4 + 2][i]),
                      .A2 (SEL1_BUF[q*4 + 2]),
                      .B1 (Do0_pre[q*4 + 3][i]),
                      .B2 (SEL1_BUF[q*4 + 3]),
                      .Y  (Do1_pre[q*2 + 1][i])
                );
            end
        end

        // Merge the four active-low pair hits into the selected bit.
        for (i = 0; i < WSIZE; i = i + 1) begin : OUT_NAND
            NAND4 QUAD_NAND (
                .A(Do1_pre[0][i]),
                .B(Do1_pre[1][i]),
                .C(Do1_pre[2][i]),
                .D(Do1_pre[3][i]),
                .Y(Do0[i])
            );
        end
    endgenerate

endmodule
