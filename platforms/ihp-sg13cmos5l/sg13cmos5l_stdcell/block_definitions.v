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

// Building blocks for the IHP SG13G2 standard cell library (sg13cmos5l_stdcell).
// platforms/ihp-sg13cmos5l/sg13cmos5l_stdcell/block_definitions.v is this
// file with the cell prefix renamed: the two libraries share cell names,
// pins and geometry.
//
// Only the blocks needed by the cfgmem_ihp / cfgmem_ihp_left models (decoders,
// buffers, antenna diodes, ties and the CFG_WORD latch row) are provided. The
// BYTE/WORD/MUX/OUTREG/RFWORD blocks used by the generic `ram` and `rf` models
// have NOT been ported to this library.
//
// Cell notes (from sg13cmos5l_stdcell.lef / .lib):
//   sg13cmos5l_dlhq_1    D latch, transparent while GATE is high (D, GATE, Q)
//   sg13cmos5l_nor2b_1   Y = !(A | !B_N)  == !A & B_N
//   sg13cmos5l_and{2,3,4}_1  plain AND gates (no inverted-input AND variants exist)
//   sg13cmos5l_antennanp antenna diode, pin A
//   sg13cmos5l_tiehi / sg13cmos5l_tielo   L_HI / L_LO
//   sg13cmos5l_buf_N     plain buffers; the library has no dedicated clock buffers
`default_nettype none

module DEC1x2 (
    input           EN,
    input           A,
    output [1:0]    SEL
);
    sg13cmos5l_nor2b_1 AND0 ( .Y(SEL[0]), .A(A),   .B_N(EN) ); // !A & EN
    sg13cmos5l_and2_1  AND1 ( .X(SEL[1]), .A(A),   .B(EN) );   //  A & EN
endmodule

module DEC2x4 (
    input           EN,
    input   [1:0]   A,
    output  [3:0]   SEL
);
    wire [1:0] A_N;
    sg13cmos5l_inv_1  INV0 ( .Y(A_N[0]), .A(A[0]) );
    sg13cmos5l_inv_1  INV1 ( .Y(A_N[1]), .A(A[1]) );

    sg13cmos5l_and3_1 AND0 ( .X(SEL[0]), .A(A_N[0]), .B(A_N[1]), .C(EN) ); // 00
    sg13cmos5l_and3_1 AND1 ( .X(SEL[1]), .A(A[0]),   .B(A_N[1]), .C(EN) ); // 01
    sg13cmos5l_and3_1 AND2 ( .X(SEL[2]), .A(A_N[0]), .B(A[1]),   .C(EN) ); // 10
    sg13cmos5l_and3_1 AND3 ( .X(SEL[3]), .A(A[0]),   .B(A[1]),   .C(EN) ); // 11
endmodule

module DEC3x8 (
    input           EN,
    input [2:0]     A,
    output [7:0]    SEL
);
    wire [2:0]  A_buf;
    wire [2:0]  A_N;
    wire        EN_buf;

    sg13cmos5l_buf_2 ABUF[2:0] ( .X(A_buf), .A(A) );
    sg13cmos5l_buf_2 ENBUF     ( .X(EN_buf), .A(EN) );

    sg13cmos5l_inv_1 INV0 ( .Y(A_N[0]), .A(A_buf[0]) );
    sg13cmos5l_inv_1 INV1 ( .Y(A_N[1]), .A(A_buf[1]) );
    sg13cmos5l_inv_1 INV2 ( .Y(A_N[2]), .A(A_buf[2]) );

    (* keep = "true" *)
    sg13cmos5l_and4_1 AND0 ( .X(SEL[0]), .A(A_N[0]),   .B(A_N[1]),   .C(A_N[2]),   .D(EN_buf) ); // 000
    sg13cmos5l_and4_1 AND1 ( .X(SEL[1]), .A(A_buf[0]), .B(A_N[1]),   .C(A_N[2]),   .D(EN_buf) ); // 001
    sg13cmos5l_and4_1 AND2 ( .X(SEL[2]), .A(A_N[0]),   .B(A_buf[1]), .C(A_N[2]),   .D(EN_buf) ); // 010
    sg13cmos5l_and4_1 AND3 ( .X(SEL[3]), .A(A_buf[0]), .B(A_buf[1]), .C(A_N[2]),   .D(EN_buf) ); // 011
    sg13cmos5l_and4_1 AND4 ( .X(SEL[4]), .A(A_N[0]),   .B(A_N[1]),   .C(A_buf[2]), .D(EN_buf) ); // 100
    sg13cmos5l_and4_1 AND5 ( .X(SEL[5]), .A(A_buf[0]), .B(A_N[1]),   .C(A_buf[2]), .D(EN_buf) ); // 101
    sg13cmos5l_and4_1 AND6 ( .X(SEL[6]), .A(A_N[0]),   .B(A_buf[1]), .C(A_buf[2]), .D(EN_buf) ); // 110
    sg13cmos5l_and4_1 AND7 ( .X(SEL[7]), .A(A_buf[0]), .B(A_buf[1]), .C(A_buf[2]), .D(EN_buf) ); // 111
endmodule

module DEC4x16 (
    input   [3:0]   A,
    input           EN,
    output  [15:0]  SEL
);
    wire [1:0]  EN0;
    DEC3x8 D0 ( .A(A[2:0]), .SEL(SEL[7:0]),  .EN(EN0[0]) );
    DEC3x8 D1 ( .A(A[2:0]), .SEL(SEL[15:8]), .EN(EN0[1]) );

    DEC1x2 D ( .A(A[3:3]), .SEL(EN0), .EN(EN) );
endmodule

module DEC5x32 (
    input   [4:0]   A,
    output  [31:0]  SEL
);
    wire [3:0]  EN;
    DEC3x8 D0 ( .A(A[2:0]), .SEL(SEL[7:0]),   .EN(EN[0]) );
    DEC3x8 D1 ( .A(A[2:0]), .SEL(SEL[15:8]),  .EN(EN[1]) );
    DEC3x8 D2 ( .A(A[2:0]), .SEL(SEL[23:16]), .EN(EN[2]) );
    DEC3x8 D3 ( .A(A[2:0]), .SEL(SEL[31:24]), .EN(EN[3]) );

    wire hi;
    sg13cmos5l_tiehi TIE ( .L_HI(hi) );

    DEC2x4 D ( .A(A[4:3]), .SEL(EN), .EN(hi) );
endmodule

module CLKBUF_2 (input A, output X);
    sg13cmos5l_buf_2 __cell__ ( .A(A), .X(X) );
endmodule

module CLKBUF_4 (input A, output X);
    sg13cmos5l_buf_4 __cell__ ( .A(A), .X(X) );
endmodule

module CLKBUF_16 (input A, output X);
    sg13cmos5l_buf_16 __cell__ ( .A(A), .X(X) );
endmodule

module DIODE (input DIODE);
    sg13cmos5l_antennanp __cell__ ( .A(DIODE) );
endmodule

module CONB (output HI, output LO);
    sg13cmos5l_tielo __cell__    ( .L_LO(LO) );
    sg13cmos5l_tiehi __cell_hi__ ( .L_HI(HI) );
endmodule

module EBUFN_2 (input A, input TE_B, output Z);
    sg13cmos5l_ebufn_4 __cell__ ( .A(A), .TE_B(TE_B), .Z(Z) );
endmodule

// Gate wrappers used by the cfgmem_ihp models, so the same model works with
// every IHP library that provides these cells (sg13g2, sg13cmos5l).
module AND2_1 (input A, input B, output X);
    sg13cmos5l_and2_1 __cell__ ( .A(A), .B(B), .X(X) );
endmodule

module AND2_2 (input A, input B, output X);
    sg13cmos5l_and2_2 __cell__ ( .A(A), .B(B), .X(X) );
endmodule

module A22OI_1 (input A1, input A2, input B1, input B2, output Y);
    sg13cmos5l_a22oi_1 __cell__ ( .A1(A1), .A2(A2), .B1(B1), .B2(B2), .Y(Y) );
endmodule

module NAND4_1 (input A, input B, input C, input D, output Y);
    sg13cmos5l_nand4_1 __cell__ ( .A(A), .B(B), .C(C), .D(D), .Y(Y) );
endmodule

module MUX2_2 (input A0, input A1, input S, output X);
    sg13cmos5l_mux2_2 __cell__ ( .A0(A0), .A1(A1), .S(S), .X(X) );
endmodule

// One 32-bit configuration word: 32 transparent latches sharing a load enable.
module CFG_WORD (
    input   wire        LE0,
    input   wire [31:0] Di0,
    output  wire [31:0] Do0
);
    generate
        genvar i;
`ifndef NO_DIODES
        (* keep = "true" *)
        sg13cmos5l_antennanp DIODE_LE0 ( .A(LE0) );
`endif
        for (i = 0; i < 32; i = i + 1) begin : CFG_BIT
            sg13cmos5l_dlhq_1 STORAGE ( .Q(Do0[i]), .D(Di0[i]), .GATE(LE0) );
        end
    endgenerate
endmodule
