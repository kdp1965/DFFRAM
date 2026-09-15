// Tiny Tapeout (CMOS5L) tile trial: one CFGMEM_IHP16 macro programmed and
// read back through an SPI slave. Exists to exercise tile-level place and
// route over the macro (Metal3/Metal4 route-through) and its power hookup.
//
// SPI: mode 0 (CPOL=0, CPHA=0), MSB first, chip select active low.
//   ui_in[0] = SCK   ui_in[1] = MOSI   ui_in[2] = CS_n   uo_out[0] = MISO
// Frames are 5 bytes: a command byte followed by 32 data bits.
//   0x01 LOAD  d[31:0]  shift the word into the macro (16 row pulses)
//   0x02 CTRL  d[5:0]   {BYP, EN0, A0[3:0]} read controls
//   0x03 READ           the selected word is shifted out on MISO during the
//                       32 data bits (sampled when the command byte completes)
// Live observation of the selected word: uo_out[7:2] = Do0[21:16],
// uio_out = Do0[15:8]; uo_out[1] is high while a LOAD is in progress.
`default_nettype none

module tt_um_cfgmem_trial (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    localparam [7:0] CMD_LOAD = 8'h01;
    localparam [7:0] CMD_CTRL = 8'h02;
    localparam [7:0] CMD_READ = 8'h03;

    // ---- SPI input synchronisers and edge detection -----------------------
    reg [2:0] sck_q, mosi_q, csn_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_q  <= 3'b000;
            mosi_q <= 3'b000;
            csn_q  <= 3'b111;
        end else begin
            sck_q  <= {sck_q[1:0],  ui_in[0]};
            mosi_q <= {mosi_q[1:0], ui_in[1]};
            csn_q  <= {csn_q[1:0],  ui_in[2]};
        end
    end
    wire sck_rise  =  sck_q[1] & ~sck_q[2];
    wire sck_fall  = ~sck_q[1] &  sck_q[2];
    wire cs_active = ~csn_q[1];
    wire mosi      =  mosi_q[1];

    // ---- frame receiver ---------------------------------------------------
    reg  [5:0]  bitcnt;
    reg  [7:0]  cmd;
    reg  [31:0] shreg;
    reg  [31:0] rd_shift;
    reg         miso;
    reg         frame_done;
    wire [31:0] do0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bitcnt     <= 6'd0;
            cmd        <= 8'h00;
            shreg      <= 32'h0;
            rd_shift   <= 32'h0;
            miso       <= 1'b0;
            frame_done <= 1'b0;
        end else begin
            frame_done <= 1'b0;
            if (!cs_active) begin
                bitcnt <= 6'd0;
                miso   <= 1'b0;
            end else begin
                if (sck_rise) begin
                    if (bitcnt < 6'd8) begin
                        cmd <= {cmd[6:0], mosi};
                        if (bitcnt == 6'd7 && {cmd[6:0], mosi} == CMD_READ)
                            rd_shift <= do0;
                    end else begin
                        shreg <= {shreg[30:0], mosi};
                    end
                    if (bitcnt == 6'd39)
                        frame_done <= 1'b1;
                    if (bitcnt != 6'd40)
                        bitcnt <= bitcnt + 6'd1;
                end
                if (sck_fall && bitcnt >= 6'd8 && cmd == CMD_READ) begin
                    miso     <= rd_shift[31];
                    rd_shift <= {rd_shift[30:0], 1'b0};
                end
            end
        end
    end

    // ---- read controls ----------------------------------------------------
    reg       byp, en;
    reg [3:0] addr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            byp  <= 1'b0;
            en   <= 1'b1;
            addr <= 4'd0;
        end else if (frame_done && cmd == CMD_CTRL) begin
            {byp, en, addr} <= shreg[5:0];
        end
    end

    // ---- shift loader: WE0 high, one-hot WROW pulses from row 15 to row 0 --
    localparam [1:0] IDLE = 2'd0, SHIFT = 2'd1, WAIT = 2'd2, NEXT = 2'd3;
    reg [1:0]  state;
    reg [3:0]  index;
    reg        we;
    reg [15:0] wrow;
    reg [31:0] word;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            index <= 4'd0;
            we    <= 1'b0;
            wrow  <= 16'h0;
            word  <= 32'h0;
        end else begin
            case (state)
                IDLE: begin
                    wrow <= 16'h0;
                    if (frame_done && cmd == CMD_LOAD) begin
                        word  <= shreg;
                        we    <= 1'b1;
                        index <= 4'd15;
                        state <= SHIFT;
                    end
                end
                SHIFT: begin
                    wrow  <= 16'h1 << index;   // registered: glitch free
                    state <= WAIT;
                end
                WAIT: begin
                    wrow  <= 16'h0;
                    state <= NEXT;
                end
                NEXT: begin
                    if (index == 4'd0) begin
                        we    <= 1'b0;
                        state <= IDLE;
                    end else begin
                        index <= index - 4'd1;
                        state <= SHIFT;
                    end
                end
            endcase
        end
    end

    // ---- the macro --------------------------------------------------------
    CFGMEM_IHP16 cfgmem (
        .WE0  (we),
        .WROW (wrow),
        .EN0  (en),
        .BYP  (byp),
        .A0   (addr),
        .Di0  (word),
        .Do0  (do0)
    );

    assign uo_out  = {do0[21:16], state != IDLE, miso};
    assign uio_out = do0[15:8];
    assign uio_oe  = 8'hFF;

    wire _unused = &{ena, uio_in, do0[31:22], do0[7:0], 1'b0};
endmodule
