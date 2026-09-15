/*
    Copyright ©2020-2022 The American University in Cairo

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

// 16 x 32 Config MEM for the IHP standard cell libraries (sg13g2, sg13cmos5l).
//
// Same architecture as models/cfgmem (sky130): a 16-deep shift chain of
// 32-bit latch words, a one-hot 16:1 read-out per bit, and a bypass mux.
// The read-out aggregation is built from IHP cells via the wrappers in the
// platform's block_definitions.v: the IHP libraries have no a222oi/a21boi, so
// each group of four words uses two a22oi_1 plus an and2_1 to form an
// active-low "quad hit", and a nand4_1 merges the four quads.
`default_nettype none

module CFGMEM_IHP16
#(
    parameter WSIZE = 32,
    parameter COUNT = 16
 )
(
    input   wire                 WE0,
    input   wire [15:0]          WROW,
    input                        EN0,
    input   wire                 BYP,
    input   wire [3:0]           A0,
    input   wire [31:0]          Di0,
    output  wire [31:0]          Do0
);
    wire [15:0]          SEL1;
    wire [15:0]          SEL1_BUF;
    wire [15:0]          LE0;
    wire [3:0]           A0_buf;
    wire                 BYP_buf;

    wire [31:0]          Di0_in[15:0];
    wire [31:0]          Do0_pre[15:0];
    wire [31:0]          Do1_pre0[3:0];   // !(D0&S0 | D1&S1)
    wire [31:0]          Do1_pre1[3:0];   // !(D2&S2 | D3&S3)
    wire [31:0]          Do1_pre[3:0];    // active-low quad hit
    wire [31:0]          nand_out;

`ifndef NO_DIODES
    (* keep = "true" *)
    DIODE    DIODE_A0 [3:0]    (.DIODE(A0[3:0]));
`endif

    CLKBUF_2   A0BUF[3:0]      (.X(A0_buf),  .A(A0[3:0]));
    CLKBUF_2   BYPBUF          (.X(BYP_buf), .A(BYP));

    DEC4x16 DEC0 (.EN(EN0), .A(A0_buf), .SEL(SEL1));

    // Chain the 16 words: word i is loaded from the output of word i-1.
    assign Di0_in[0] = Di0;
    generate
        genvar i;
        for (i = 1; i < 16; i = i + 1) begin : IN_MAP
            assign Di0_in[i] = Do0_pre[i-1];
        end

        // 16 word rows, each with a read-select buffer, protection diode and
        // the AND that forms the row load enable from WROW & WE0.
        for (i = 0; i < 16; i = i + 1) begin : SLICE
            CFG_WORD CWORD (.LE0(LE0[i]), .Di0(Di0_in[i]), .Do0(Do0_pre[i]));
            CLKBUF_4 SELBUF     (.X(SEL1_BUF[i]), .A(SEL1[i]));
            (* keep = "true" *)
            DIODE    DIODE_SEL1 (.DIODE(SEL1_BUF[i]));
            AND2_2   ROW_AND    (.X(LE0[i]), .A(WROW[i]), .B(WE0));
        end
    endgenerate

    // Per group of four words: quad hit (active low) =
    //   !((D0&S0) | (D1&S1)) & !((D2&S2) | (D3&S3))
    generate
        genvar q;
        for (q = 0; q < 4; q = q + 1) begin : QUADS
            for (i = 0; i < 32; i = i + 1) begin : QBIT
                A22OI_1 QUAD_A22OI0 (
                      .A1 (Do0_pre[q*4 + 0][i]),
                      .A2 (SEL1_BUF[q*4 + 0]),
                      .B1 (Do0_pre[q*4 + 1][i]),
                      .B2 (SEL1_BUF[q*4 + 1]),
                      .Y  (Do1_pre0[q][i])
                );
                A22OI_1 QUAD_A22OI1 (
                      .A1 (Do0_pre[q*4 + 2][i]),
                      .A2 (SEL1_BUF[q*4 + 2]),
                      .B1 (Do0_pre[q*4 + 3][i]),
                      .B2 (SEL1_BUF[q*4 + 3]),
                      .Y  (Do1_pre1[q][i])
                );
                AND2_1 QUAD_AND (
                      .A  (Do1_pre0[q][i]),
                      .B  (Do1_pre1[q][i]),
                      .X  (Do1_pre[q][i])
                );
            end
        end

        for (i = 0; i < 32; i = i + 1) begin : OUT_NAND
            // Merge the four active-low quad hits into the selected bit.
            NAND4_1 QUAD_NAND (
                .A(Do1_pre[0][i]),
                .B(Do1_pre[1][i]),
                .C(Do1_pre[2][i]),
                .D(Do1_pre[3][i]),
                .Y(nand_out[i])
            );

            // Final output: bypass straight from Di0 when BYP is set.
            MUX2_2 OUT_MUX (
                .A0(nand_out[i]),
                .A1(Di0[i]),
                .S (BYP_buf),
                .X (Do0[i])
            );
        end
    endgenerate

endmodule
