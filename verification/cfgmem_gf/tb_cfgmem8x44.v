// Self-checking Icarus bench for the CFGMEM8x44 macro (models/cfgmem_gf):
// the RTL model built from the gf180 block definitions (make rtl) and the
// routed netlist (make nl NL=<pnl.v>, with power pins) see the same stimulus.
//
// Load protocol (latch_loader.v in the PRISM tile): WE0 high, then WROW
// pulsed one-hot from row 7 down to row 0.  Row k copies row k-1 and row 0
// copies Di0, so eight pulses shift one word in and every older word one row
// up.  Reads are asynchronous: Do0 = word[A0] while EN0 is high.
`timescale 1ns / 1ps
module tb_cfgmem8x44;
   reg         we0 = 0;
   reg  [7:0]  wrow = 0;
   reg         en0 = 1;
   reg  [2:0]  a0 = 0;
   reg  [43:0] di = 0;
   wire [43:0] dout;
   supply1 vpwr;
   supply0 vgnd;

`ifdef POWER_PINS
   CFGMEM8x44 dut (.WE0(we0), .WROW(wrow), .EN0(en0), .A0(a0), .Di0(di), .Do0(dout), .VPWR(vpwr), .VGND(vgnd));
`else
   CFGMEM8x44 dut (.WE0(we0), .WROW(wrow), .EN0(en0), .A0(a0), .Di0(di), .Do0(dout));
`endif

   reg [43:0] ref_word [0:7];
   reg [7:0]  valid = 0;
   integer    fails = 0, checks = 0, i, k;
   reg [63:0] rnd;

   // one WROW pulse: ~31 ns high (one tile clock), then a two-clock gap
   task pulse_row(input integer row);
   begin
      wrow = 8'b1 << row; #31; wrow = 0; #62;
   end
   endtask

   // the tile's load: Di0 stable, WE0 up, rows 7..0 pulsed, WE0 down
   task load(input [43:0] w);
   begin
      di = w; #15; we0 = 1; #15;
      for (k = 7; k >= 0; k = k - 1) pulse_row(k);
      we0 = 0; #15;
      for (k = 7; k > 0; k = k - 1) begin ref_word[k] = ref_word[k-1]; valid[k] = valid[k-1]; end
      ref_word[0] = w; valid[0] = 1;
   end
   endtask

   task check_all(input [8*16-1:0] what);
      integer r;
   begin
      for (r = 0; r < 8; r = r + 1) if (valid[r]) begin
         a0 = r; #20; checks = checks + 1;
         if (dout !== ref_word[r]) begin
            fails = fails + 1;
            $display("  FAIL %0s row %0d: got %h want %h", what, r, dout, ref_word[r]);
         end
      end
   end
   endtask

   initial begin
      #100;
      // 1. fill the eight rows, checking every loaded row after each load
      for (i = 0; i < 8; i = i + 1) begin
         rnd = {$random, $random}; load(rnd[43:0]); check_all("fill");
      end
      // 2. eight more: the first eight shift out through row 7
      for (i = 0; i < 8; i = i + 1) begin
         rnd = {$random, $random}; load(rnd[43:0]); check_all("shift");
      end
      // 3. controls: WROW pulses without WE0 change nothing
      di = 44'h0; #15;
      for (k = 7; k >= 0; k = k - 1) pulse_row(k);
      check_all("wrow_no_we");
      // WE0 without a pulse changes nothing
      we0 = 1; #100; we0 = 0; #15;
      check_all("we_no_wrow");
      // a single row pulse copies only its upper neighbour into it
      we0 = 1; #15; pulse_row(5); we0 = 0; #15;
      ref_word[5] = ref_word[4];
      check_all("single_row");
      // EN0 low reads zero
      en0 = 0; #20;
      for (k = 0; k < 8; k = k + 1) begin
         a0 = k; #20; checks = checks + 1;
         if (dout !== 44'h0) begin fails = fails + 1; $display("  FAIL en0_low row %0d: got %h", k, dout); end
      end
      en0 = 1; #20;
      check_all("en0_back");
      // 4. all-ones and all-zeros patterns through the chain
      load({44{1'b1}}); check_all("ones");
      load(44'h0);      check_all("zeros");
      load(44'h5555_5555_555); check_all("5s");
      load(44'haaaa_aaaa_aaa); check_all("as");
      if (fails == 0) $display("CFGMEM8x44: ALL PASSED (%0d checks)", checks);
      else            $display("CFGMEM8x44: %0d FAILED of %0d checks", fails, checks);
      $finish;
   end
endmodule
