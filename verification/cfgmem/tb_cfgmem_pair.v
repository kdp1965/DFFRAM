// Two CFGMEM16 macros chained the way the PRISM peripheral chains them:
// the "hi" macro's data input is the "lo" macro's read output, and both
// share the row-select bus. The macro module names are passed in with
// -DCFGMEM_RIGHT=... -DCFGMEM_LEFT=... so the same bench runs on the sky130,
// sg13g2 and sg13cmos5l RTL models and gate-level netlists.
`default_nettype none

module tb_cfgmem_pair (
    input  wire        we_lo,
    input  wire        we_hi,
    input  wire [15:0] wrow,
    input  wire        en_lo,
    input  wire        en_hi,
    input  wire        byp_lo,
    input  wire        byp_hi,
    input  wire [3:0]  a_lo,
    input  wire [3:0]  a_hi,
    input  wire [31:0] di,
    output wire [31:0] do_lo,
    output wire [31:0] do_hi
);
    `CFGMEM_RIGHT lo (
        .WE0  (we_lo),
        .WROW (wrow),
        .EN0  (en_lo),
        .BYP  (byp_lo),
        .A0   (a_lo),
        .Di0  (di),
        .Do0  (do_lo)
    );

    `CFGMEM_LEFT hi (
        .WE0  (we_hi),
        .WROW (wrow),
        .EN0  (en_hi),
        .BYP  (byp_hi),
        .A0   (a_hi),
        .Di0  (do_lo),
        .Do0  (do_hi)
    );
endmodule
