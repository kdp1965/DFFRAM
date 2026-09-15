// Blackbox declaration of the CFGMEM_IHP16 hard macro for linting only; the
// flow takes the real views from the MACROS configuration.
(* blackbox *)
module CFGMEM_IHP16 (
    input  wire        WE0,
    input  wire [15:0] WROW,
    input  wire        EN0,
    input  wire        BYP,
    input  wire [3:0]  A0,
    input  wire [31:0] Di0,
    output wire [31:0] Do0
);
endmodule
