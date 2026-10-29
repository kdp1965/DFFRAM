/*
    RAM32 with an AND-OR read path (see BYTE_AO / WORD_AO and the NAND4 /
    OR4 wrappers in a platform's block_definitions.v: sky130A, sky130B,
    gf180mcuD).  Same ports as models/ram's RAM32.

    Read path per bit: 8 x nand2 (one per word, ~(Q & SEL)) -> 2 x nand4
    (the slice's two word quads) -> or4 (the 16-word block's two slices)
    -> OUTREG -> MUX2x1 (the two blocks).  Nothing floats: with no word
    selected every nand2 is 1, the nand4s are 0 and the block reads 0,
    which is what models/ram's float buffers tied the bus to.  2026-10-16.
*/
`timescale 1ns / 1ps
`default_nettype none

module RAM8_AO #( parameter    USE_LATCH=1,
                               WSIZE=1 ) (
    input   wire                 CLK,    // FO: 1
    input   wire [WSIZE-1:0]     WE0,    // FO: 1
    input                        EN0,    // EN0: 1
    input   wire [2:0]           A0,     // A: 1
    input   wire [(WSIZE*8-1):0] Di0,    // FO: 1
    output  wire [(WSIZE*8-1):0] PLO,    // ~AND of words 0-3's terms: 1 when one of them is selected with a 1
    output  wire [(WSIZE*8-1):0] PHI     // the same for words 4-7
);
    wire    [7:0]         SEL0;
    wire    [WSIZE-1:0]   WE0_buf;
    wire                  CLK_buf;
    wire    [8*WSIZE*8-1:0] Qn;           // word w's terms at Qn[w*WSIZE*8 +: WSIZE*8]

    DEC3x8 DEC0 (.EN(EN0), .A(A0), .SEL(SEL0));
    CLKBUF_2 WEBUF[WSIZE-1:0] (.X(WE0_buf), .A(WE0));
    CLKBUF_2 CLKBUF (.X(CLK_buf), .A(CLK));

    generate
        genvar i, h;
        for (i=0; i< 8; i=i+1) begin : WORD
            WORD_AO #(.USE_LATCH(USE_LATCH), .WSIZE(WSIZE)) W ( .CLK(CLK_buf), .WE0(WE0_buf), .SEL0(SEL0[i]), .Di0(Di0), .Qn0(Qn[i*WSIZE*8 +: WSIZE*8]) );
        end
        for (i=0; i< WSIZE*8; i=i+1) begin : BIT
            for (h=0; h< 2; h=h+1) begin : HALF
                wire y;
                NAND4 N4 ( .A(Qn[(4*h+0)*WSIZE*8 + i]), .B(Qn[(4*h+1)*WSIZE*8 + i]), .C(Qn[(4*h+2)*WSIZE*8 + i]), .D(Qn[(4*h+3)*WSIZE*8 + i]), .Y(y) );
                if (h == 0) begin : LO
                    assign PLO[i] = y;
                end else begin : HI
                    assign PHI[i] = y;
                end
            end
        end
    endgenerate
endmodule

module RAM16_AO #( parameter   USE_LATCH=1,
                               WSIZE=1 )
(
    input   wire                 CLK,    // FO: 2
    input   wire [WSIZE-1:0]     WE0,    // FO: 1
    input                        EN0,    // FO: 1
    input   wire [3:0]           A0,     // FO: 1
    input   wire [(WSIZE*8-1):0] Di0,    // FO: 1
    output  wire [(WSIZE*8-1):0] Do0
);
    wire [1:0]           SEL0;
    wire [3:0]           A0_buf;
    wire                 CLK_buf;
    wire [WSIZE-1:0]     WE0_buf;
    wire                 EN0_buf;
    wire [WSIZE*8-1:0]   Do0_pre;
    wire [2*WSIZE*8-1:0] PLO;            // slice s's terms at PLO[s*WSIZE*8 +: WSIZE*8]
    wire [2*WSIZE*8-1:0] PHI;

`ifndef NO_DIODES
    (* keep = "true" *)
    DIODE    DIODE_CLK         (.DIODE(CLK));
`endif
    CLKBUF_4   CLKBUF              (.X(CLK_buf), .A(CLK));
    CLKBUF_2   WEBUF[(WSIZE-1):0]  (.X(WE0_buf), .A(WE0));
`ifndef NO_DIODES
    (* keep = "true" *)
    DIODE    DIODE_A0 [3:0]    (.DIODE(A0[3:0]));
`endif
    CLKBUF_2   A0BUF[3:0]           (.X(A0_buf),  .A(A0[3:0]));
    CLKBUF_2   EN0BUF               (.X(EN0_buf), .A(EN0));

    DEC1x2 DEC0 (.EN(EN0_buf), .A(A0_buf[3:3]), .SEL(SEL0));

    generate
        genvar i;
        for (i=0; i< 2; i=i+1) begin : SLICE
            RAM8_AO #(.USE_LATCH(USE_LATCH), .WSIZE(WSIZE)) RAM8 (.CLK(CLK_buf), .WE0(WE0_buf), .EN0(SEL0[i]), .Di0(Di0), .A0(A0_buf[2:0]), .PLO(PLO[i*WSIZE*8 +: WSIZE*8]), .PHI(PHI[i*WSIZE*8 +: WSIZE*8]) );
        end
        for (i=0; i< WSIZE*8; i=i+1) begin : BIT
            OR4 OR4 ( .A(PLO[i]), .B(PHI[i]), .C(PLO[WSIZE*8 + i]), .D(PHI[WSIZE*8 + i]), .X(Do0_pre[i]) );
        end
    endgenerate

    OUTREG #(.WIDTH(WSIZE*8)) Do0_REG ( .CLK(CLK_buf), .Di(Do0_pre), .Do(Do0) );
endmodule

module RAM32 #( parameter    USE_LATCH=1,
                             WSIZE=4 )
(
    input   wire                 CLK,     // FO: 2
    input   wire [WSIZE-1:0]     WE0,     // FO: 1
    input                        EN0,     // FO: 1
    input   wire [4:0]           A0,      // FO: 1
    input   wire [(WSIZE*8-1):0] Di0,     // FO: 1
    output  wire [(WSIZE*8-1):0] Do0
);
    wire                    EN0_buf;
    wire [1:0]              SEL0;
    wire [4:0]              A0_buf;
    wire [(WSIZE-1):0]      WE0_buf;
    wire [(WSIZE*8-1):0]    Do0_pre[1:0];
    wire [(WSIZE*8-1):0]    Di0_buf;

    CLKBUF_16  DIBUF[(WSIZE*8-1):0] (.X(Di0_buf), .A(Di0));
    CLKBUF_2   WEBUF[(WSIZE-1):0]   (.X(WE0_buf), .A(WE0));
    CLKBUF_2   A0BUF[4:0]           (.X(A0_buf),  .A(A0[4:0]));
    CLKBUF_2   EN0BUF               (.X(EN0_buf), .A(EN0));

    DEC1x2 DEC0 (.EN(EN0_buf), .A(A0_buf[4]), .SEL(SEL0));

    generate
        genvar i;
        for (i=0; i< 2; i=i+1) begin : SLICE_16
            RAM16_AO #(.USE_LATCH(USE_LATCH), .WSIZE(WSIZE)) RAM16 (.CLK(CLK), .EN0(SEL0[i]), .WE0(WE0_buf), .Di0(Di0_buf), .Do0(Do0_pre[i]), .A0(A0_buf[3:0]) );
        end
    endgenerate

    MUX2x1 #(.WIDTH(WSIZE*8)) Do0MUX ( .A0(Do0_pre[0]), .A1(Do0_pre[1]), .S(A0_buf[4]), .X(Do0) );
endmodule
