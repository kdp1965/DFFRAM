// Verilator bench for tt_um_cfgmem_trial: a bit-banged SPI master loads words
// into the CFGMEM macro and reads them back, checked against a model.
#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include "Vtt_um_cfgmem_trial.h"
#include "verilated.h"

namespace {
struct Tb {
    Vtt_um_cfgmem_trial* d;
    uint64_t cyc = 0;
    int errors = 0, checks = 0;
    uint32_t mem[16]; bool valid[16];
    unsigned byp = 0, en = 1, addr = 0;
    std::mt19937 rng{1};

    explicit Tb(Vtt_um_cfgmem_trial* dut) : d(dut) { for (auto& v : valid) v = false; }

    void tick() { d->clk = 0; d->eval(); d->clk = 1; d->eval(); cyc++; }
    void set_pins(int sck, int mosi, int csn) { d->ui_in = (csn << 2) | (mosi << 1) | sck; }
    // SPI mode 0: MOSI set before the rising edge, MISO sampled on the rising edge.
    int xfer_bit(int mosi) {
        set_pins(0, mosi, 0); for (int i = 0; i < 4; i++) tick();
        set_pins(1, mosi, 0); tick(); tick();
        int miso = d->uo_out & 1;
        for (int i = 0; i < 2; i++) tick();
        return miso;
    }
    uint32_t frame(uint8_t cmd, uint32_t data) {
        set_pins(0, 0, 0); for (int i = 0; i < 4; i++) tick();
        for (int i = 7; i >= 0; i--) xfer_bit((cmd >> i) & 1);
        uint32_t rd = 0;
        for (int i = 31; i >= 0; i--) rd = (rd << 1) | xfer_bit((data >> i) & 1);
        set_pins(0, 0, 1); for (int i = 0; i < 6; i++) tick();
        return rd;
    }
    void load(uint32_t w) {
        frame(0x01, w);
        for (int i = 0; i < 60; i++) tick();           // 16 rows x 3 cycles
        for (int k = 15; k > 0; k--) { mem[k] = mem[k - 1]; valid[k] = valid[k - 1]; }
        mem[0] = w; valid[0] = true;
    }
    void ctrl(unsigned b, unsigned e, unsigned a) {
        byp = b; en = e; addr = a;
        frame(0x02, (b << 5) | (e << 4) | a);
        for (int i = 0; i < 4; i++) tick();
    }
    uint32_t expected() {
        if (byp) return 0;   // Di0 is the loader's word register; not modelled here
        if (!en) return 0;
        return valid[addr] ? mem[addr] : 0;
    }
    void check_read(const char* what) {
        if (byp || !valid[addr]) return;
        uint32_t got = frame(0x03, 0);
        uint32_t exp = expected();
        checks++;
        if (got != exp) { errors++; if (errors < 20) printf("FAIL %s addr %u: exp %08x got %08x\n", what, addr, exp, got); }
        // live observation pins
        uint32_t live = ((d->uo_out >> 2) & 0x3f) << 16 | (d->uio_out & 0xff) << 8;
        uint32_t expl = (exp & 0x003fff00);
        checks++;
        if (live != expl) { errors++; if (errors < 20) printf("FAIL %s live pins addr %u: exp %08x got %08x\n", what, addr, expl, live); }
    }
};
}

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    auto* dut = new Vtt_um_cfgmem_trial;
    Tb tb(dut);
    dut->rst_n = 0; dut->ena = 1; dut->uio_in = 0; tb.set_pins(0, 0, 1);
    for (int i = 0; i < 5; i++) tb.tick();
    dut->rst_n = 1;
    for (int i = 0; i < 5; i++) tb.tick();

    printf("T1 load 16 words, read all rows after each load\n");
    for (int i = 0; i < 16; i++) {
        tb.load(tb.rng());
        for (int a = 0; a < 16; a++) { tb.ctrl(0, 1, a); tb.check_read("T1"); }
    }
    printf("T2 EN0=0 reads zero; loads while reading a fixed row\n");
    tb.ctrl(0, 0, 3);
    uint32_t got = tb.frame(0x03, 0); tb.checks++;
    if (got != 0) { tb.errors++; printf("FAIL T2 EN0=0: got %08x\n", got); }
    tb.ctrl(0, 1, 7);
    for (int i = 0; i < 8; i++) { tb.load(tb.rng()); tb.check_read("T2"); }
    printf("T3 random loads and reads\n");
    for (int i = 0; i < 40; i++) {
        if (tb.rng() % 3 == 0) tb.load(tb.rng());
        tb.ctrl(0, 1, tb.rng() % 16);
        tb.check_read("T3");
    }
    printf("%s: %d checks, %d errors, %llu cycles\n", tb.errors ? "FAIL" : "PASS", tb.checks, tb.errors, (unsigned long long)tb.cyc);
    dut->final(); delete dut;
    return tb.errors ? 1 : 0;
}
