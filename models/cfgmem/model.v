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

// Add 1x2 binary decoder
`default_nettype none

// 16 x 32 Config MEM
module CFGMEM16
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
    wire [15:0]          LE0_pre;
    wire [3:0]           A0_buf;
    wire                 BYP_buf;
    wire                 EN0_buf;
    wire                 WE0_DLY;

    wire [31:0]          Di0_in[15:0];
    wire [31:0]          Do0_pre[15:0];
    wire [31:0]          Do1_pre0[3:0];
    wire [31:0]          Do1_pre[3:0];
    wire [31:0]          nand_out;

`ifndef NO_DIODES   
    (* keep = "true" *)
    DIODE    DIODE_A0 [3:0]    (.DIODE(A0[3:0]));
`endif
    
    CLKBUF_2   A0BUF[3:0]      (.X(A0_buf),  .A(A0[3:0]));
    CLKBUF_2   BYPBUF          (.X(BYP_buf), .A(BYP));

    DEC4x16 DEC0 (.EN(EN0), .A(A0_buf), .SEL(SEL1));
    
    // Create CFG_WORDs for all 16 rows
    assign Di0_in[0] = Di0;
    generate
        genvar i;
        for (i=1; i< 16; i=i+1) begin : IN_MAP
            assign Di0_in[i] = Do0_pre[i-1];
        end

        // Create 16 rows of WORDS plus SEL buffers with protection diodes.
        for (i=0; i< 16; i=i+1) begin : SLICE
            CFG_WORD CWORD (.LE0(LE0[i]), .Di0(Di0_in[i]), .Do0(Do0_pre[i]) ); 
            sky130_fd_sc_hd__clkbuf_4 SELBUF (.X(SEL1_BUF[i]), .A(SEL1[i]));
            sky130_fd_sc_hd__diode_2 DIODE_SEL1 (.DIODE(SEL1_BUF[i]));
            sky130_fd_sc_hd__and2_2  ROW_AND (.X(LE0[i]), .A(WROW[i]), .B(WE0));
        end
    endgenerate

    // Create 4 aggregator circuts for each group of 4 WORDS using an a222oi
    // and an a21boi.  This result in 1 signal that must feed into a 4-input
    // NAND somewhere.
    //
    // a222oi: Y = !((A1 & A2) | (B1 & B2) | (C1 & C2))
    // a21boi: Y = !((A1 & A2) | (!B1_N))
    generate
        genvar q;
        for (q = 0; q < 4; q=q+1) begin : QUADS
            for (i = 0; i < 32; i=i+1) begin : QBIT
                sky130_fd_sc_hd__a222oi_1 QUAD_A222OI (
                      .A1 (Do0_pre[q*4  + 1][i]),
                      .B1 (Do0_pre[q*4  + 2][i]),
                      .C1 (Do0_pre[q*4  + 3][i]),
                      .A2 (SEL1_BUF[q*4 + 1]),
                      .B2 (SEL1_BUF[q*4 + 2]),
                      .C2 (SEL1_BUF[q*4 + 3]),
                      .Y  (Do1_pre0[q][i])
                );
                sky130_fd_sc_hd__a21boi_1 QUAD_A21BOI (
                      .A1   (Do0_pre[q*4  + 0][i]),
                      .A2   (SEL1_BUF[q*4 + 0]),
                      .B1_N (Do1_pre0[q][i]),
                      .Y    (Do1_pre[q][i])
                );
            end
        end

        for (i = 0; i < 32; i=i+1) begin : OUT_NAND
            // Create cell lookup outputs
            sky130_fd_sc_hd__nand4_1 QUAD_NAND
            (
                .A(Do1_pre[0][i]),
                .B(Do1_pre[1][i]),
                .C(Do1_pre[2][i]),
                .D(Do1_pre[3][i]),
                .Y(nand_out[i])
            );

            // Create final outputs based on input BYPass
            sky130_fd_sc_hd__mux2_2 OUT_MUX
            (
                .A0(nand_out[i]),
                .A1(Di0[i]),
                .S (BYP_buf),
                .X (Do0[i])
            );
        end
    endgenerate

endmodule

