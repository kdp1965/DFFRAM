// Verilator bench for the LRAM_IHP16x8 latch RAM.
//
// The write port follows DFFRAM's latch byte: WE / WA / Di are presented
// after a rising edge, the selected word's latches are open during the low
// phase and close on the next rising edge.  The bench therefore drives the
// inputs while clk is high, checks the asynchronous read port after the
// falling edge (the written word is already visible) and after the rising
// edge, and also checks that an enable that is not up at the falling edge
// writes nothing.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>

#include "Vtb_lram.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

struct Bench {
    VerilatedContext* ctx;
    Vtb_lram* dut;
    VerilatedVcdC* vcd = nullptr;
    uint64_t t = 0;
    std::mt19937 rng;
    int errors = 0;
    int checks = 0;
    uint8_t ref[16];

    Bench(VerilatedContext* c, Vtb_lram* d, uint32_t seed) : ctx(c), dut(d), rng(seed) {
        memset(ref, 0, sizeof ref);
        dut->clk = 1;
        dut->rst_n = 1;
        dut->we = 0;
        dut->wa = 0;
        dut->di = 0;
        dut->ra = 0;
    }

    void eval() {
        dut->eval();
        if (vcd) vcd->dump(t);
        t++;
    }

    int rnd(int n) { return std::uniform_int_distribution<int>(0, n - 1)(rng); }

    void fail(const char* what, int addr, int exp, int got) {
        errors++;
        if (errors <= 20)
            printf("FAIL: %s word %2d: expected %02x got %02x\n", what, addr, exp, got);
    }

    // clock phases: the bench rests with clk high (just after a rising edge)
    void fall() { dut->clk = 0; eval(); }
    void rise() { dut->clk = 1; eval(); }

    int read(int addr) {
        dut->ra = addr;
        eval();
        return dut->dout;
    }

    void check(int addr, const char* what) {
        int got = read(addr);
        checks++;
        if (got != ref[addr]) fail(what, addr, ref[addr], got);
    }

    void check_all(const char* what) {
        int order[16];
        for (int i = 0; i < 16; i++) order[i] = i;
        for (int i = 15; i > 0; i--) std::swap(order[i], order[rnd(i + 1)]);
        for (int i = 0; i < 16; i++) check(order[i], what);
    }

    // One clock cycle with the write port driven (we may be 0).
    void cycle(int we, int wa, int di) {
        dut->we = we;
        dut->wa = wa;
        dut->di = di;
        eval();                 // high phase: the gate enable settles
        fall();                 // low phase: the word is written
        if (we) ref[wa] = di;
        rise();                 // latches closed again
    }

    void reset() {
        dut->rst_n = 0;
        eval();
        fall();
        rise();
        dut->rst_n = 1;
        eval();
        memset(ref, 0, sizeof ref);
    }

    // ---- tests -----------------------------------------------------------

    void test_reset() {
        printf("T1  reset clears every word\n");
        // scribble first so the clear is visible
        for (int w = 0; w < 16; w++) cycle(1, w, 0xA5 ^ w);
        reset();
        check_all("after reset");
    }

    void test_fill() {
        printf("T2  write every word, read back in random order\n");
        for (int w = 0; w < 16; w++) cycle(1, w, (w * 37 + 11) & 0xFF);
        check_all("fill");
        for (int w = 15; w >= 0; w--) cycle(1, w, ~((w * 37 + 11) & 0xFF) & 0xFF);
        check_all("refill");
    }

    void test_transparent() {
        printf("T3  a write is visible on the read port from the falling edge\n");
        for (int i = 0; i < 64; i++) {
            int wa = rnd(16), di = rnd(256);
            dut->we = 1; dut->wa = wa; dut->di = di; dut->ra = wa;
            eval();
            // still the old word in the high phase
            checks++;
            if (dut->dout != ref[wa]) fail("before the falling edge", wa, ref[wa], dut->dout);
            fall();
            ref[wa] = di;
            checks++;
            if (dut->dout != ref[wa]) fail("after the falling edge", wa, ref[wa], dut->dout);
            rise();
            checks++;
            if (dut->dout != ref[wa]) fail("after the rising edge", wa, ref[wa], dut->dout);
        }
        dut->we = 0;
        eval();
    }

    void test_gate() {
        printf("T4  the enable is sampled at the falling edge\n");
        for (int i = 0; i < 64; i++) {
            int wa = rnd(16), di = ref[wa] ^ (1 + rnd(255));
            // WE up only in the high phase: nothing written
            dut->we = 1; dut->wa = wa; dut->di = di; eval();
            dut->we = 0; eval();
            fall(); rise();
            check(wa, "WE dropped before the falling edge");
            // WE up only in the low phase: nothing written either
            dut->we = 0; eval();
            fall();
            dut->we = 1; eval();
            rise();
            dut->we = 0; eval();
            check(wa, "WE raised after the falling edge");
            // WA moved after the falling edge: the first word is written
            int wb = (wa + 1 + rnd(15)) & 15;
            dut->we = 1; dut->wa = wa; dut->di = di; eval();
            fall();
            dut->wa = wb; eval();       // the gate of wa is open; wb's is not
            rise();
            dut->we = 0; eval();
            ref[wa] = di;
            check(wa, "WA moved in the low phase (written)");
            check(wb, "WA moved in the low phase (not written)");
        }
    }

    void test_random(int ops) {
        printf("T5  %d random cycles against the reference model\n", ops);
        for (int i = 0; i < ops; i++) {
            int we = rnd(4) != 0;           // three writes in four, back to back
            cycle(we, rnd(16), rnd(256));
            check(rnd(16), "random");
            if (i % 97 == 0) check_all("random sweep");
        }
    }
};

int main(int argc, char** argv) {
    auto* ctx = new VerilatedContext;
    ctx->commandArgs(argc, argv);
    ctx->traceEverOn(true);

    uint32_t seed = 1;
    int ops = 5000;
    bool trace = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a.rfind("+seed=", 0) == 0) seed = std::strtoul(a.c_str() + 6, nullptr, 0);
        else if (a.rfind("+ops=", 0) == 0) ops = std::atoi(a.c_str() + 5);
        else if (a == "+trace") trace = true;
    }

    auto* dut = new Vtb_lram(ctx);
    Bench b(ctx, dut, seed);
    if (trace) {
        b.vcd = new VerilatedVcdC;
        dut->trace(b.vcd, 99);
        b.vcd->open("tb_lram.vcd");
    }
    printf("LRAM_IHP16x8 testbench, seed %u\n", seed);
    b.reset();
    b.test_reset();
    b.test_fill();
    b.test_transparent();
    b.test_gate();
    b.test_random(ops);
    if (b.vcd) b.vcd->close();
    printf("%s: %d checks, %d errors\n", b.errors ? "FAIL" : "PASS", b.checks, b.errors);
    delete dut;
    delete ctx;
    return b.errors ? 1 : 0;
}
