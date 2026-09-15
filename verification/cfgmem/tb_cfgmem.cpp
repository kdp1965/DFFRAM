// Verilator testbench for the CFGMEM16 configuration memory macros.
//
// The device under test is tb_cfgmem_pair.v: two macros ("lo" and "hi")
// chained as the PRISM peripheral chains them (hi.Di0 = lo.Do0, shared WROW).
// A software reference model tracks the 16 words of each macro; every check
// reads back all rows through the random-access read port.
//
// Load protocol (from cfgmem_periph.v): raise WE0, then pulse WROW one-hot
// from row 15 down to row 0. Each pulse makes row k copy row k-1; row 0
// copies Di0. Sixteen pulses therefore shift one new word in and every older
// word one row up. Row 15 of "lo" can be shifted into row 0 of "hi" by
// selecting A0=15 on "lo" while "hi" is loaded, or Di0 can be passed straight
// through "lo" with BYP.

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <string>

#include "Vtb_cfgmem_pair.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

namespace {

struct Bench {
    VerilatedContext* ctx;
    Vtb_cfgmem_pair* dut;
    VerilatedVcdC* vcd = nullptr;
    uint64_t t = 0;
    std::mt19937 rng;
    int errors = 0;
    int checks = 0;

    // Reference model. valid[] is false until a row has been loaded, because
    // the latches power up in an unknown state (randomised in this bench).
    uint32_t ref[2][16];
    bool valid[2][16];

    Bench(VerilatedContext* c, Vtb_cfgmem_pair* d, uint32_t seed) : ctx(c), dut(d), rng(seed) {
        memset(ref, 0, sizeof ref);
        memset(valid, 0, sizeof valid);
        dut->we_lo = dut->we_hi = 0;
        dut->wrow = 0;
        dut->en_lo = dut->en_hi = 1;
        dut->byp_lo = dut->byp_hi = 0;
        dut->a_lo = dut->a_hi = 0;
        dut->di = 0;
    }

    void eval() {
        dut->eval();
        if (vcd) vcd->dump(t);
        t++;
    }

    uint32_t rnd32() { return rng(); }
    int rnd(int n) { return std::uniform_int_distribution<int>(0, n - 1)(rng); }

    void fail(const char* what, int m, int row, uint32_t exp, uint32_t got) {
        errors++;
        if (errors <= 20)
            printf("FAIL: %s %s row %2d: expected %08x got %08x\n", what, m ? "hi" : "lo", row, exp, got);
    }

    // ---- read port -------------------------------------------------------
    uint32_t read(int m, int addr) {
        if (m == 0) { dut->a_lo = addr; dut->en_lo = 1; dut->byp_lo = 0; }
        else        { dut->a_hi = addr; dut->en_hi = 1; dut->byp_hi = 0; }
        eval();
        return m == 0 ? dut->do_lo : dut->do_hi;
    }

    // Read every loaded row of macro m in random order and compare.
    void check(int m, const char* what) {
        int order[16];
        for (int i = 0; i < 16; i++) order[i] = i;
        for (int i = 15; i > 0; i--) std::swap(order[i], order[rnd(i + 1)]);
        for (int i = 0; i < 16; i++) {
            int row = order[i];
            if (!valid[m][row]) continue;
            uint32_t got = read(m, row);
            checks++;
            if (got != ref[m][row]) fail(what, m, row, ref[m][row], got);
        }
    }

    void check_all(const char* what) { check(0, what); check(1, what); }

    // ---- load protocol ---------------------------------------------------
    void pulse_row(int k) {
        dut->wrow = 1u << k;
        eval();
        dut->wrow = 0;
        eval();
    }

    void shift_ref(int m, uint32_t in, bool in_valid) {
        for (int k = 15; k > 0; k--) { ref[m][k] = ref[m][k - 1]; valid[m][k] = valid[m][k - 1]; }
        ref[m][0] = in;
        valid[m][0] = in_valid;
    }

    // Shift one word into "lo" from Di0.
    void load_lo(uint32_t word) {
        dut->di = word;
        dut->we_lo = 1;
        eval();
        for (int k = 15; k >= 0; k--) pulse_row(k);
        dut->we_lo = 0;
        eval();
        shift_ref(0, word, true);
    }

    // Shift "lo" row 15 into "hi" through lo's read port (A0 = 15).
    void load_hi_from_lo() {
        dut->a_lo = 15; dut->en_lo = 1; dut->byp_lo = 0;
        dut->we_hi = 1;
        eval();
        for (int k = 15; k >= 0; k--) pulse_row(k);
        dut->we_hi = 0;
        eval();
        shift_ref(1, ref[0][15], valid[0][15]);
    }

    // Shift a word into "hi" straight from Di0, bypassing "lo".
    void load_hi_bypass(uint32_t word) {
        dut->di = word;
        dut->byp_lo = 1;
        dut->we_hi = 1;
        eval();
        for (int k = 15; k >= 0; k--) pulse_row(k);
        dut->we_hi = 0;
        dut->byp_lo = 0;
        eval();
        shift_ref(1, word, true);
    }

    // ---- tests -----------------------------------------------------------
    void test_fill_lo() {
        printf("T1  shift-load 16 words into lo, checking after every load\n");
        for (int i = 0; i < 16; i++) {
            load_lo(rnd32());
            check(0, "T1");
        }
    }

    void test_chain() {
        printf("T2  shift 16 words lo -> hi through lo row 15, refilling lo\n");
        uint32_t first[16];
        for (int i = 0; i < 16; i++) first[i] = ref[0][15 - i];  // oldest first
        for (int i = 0; i < 16; i++) {
            load_hi_from_lo();
            check_all("T2a");
            load_lo(rnd32());
            check_all("T2b");
        }
        // hi must now hold the 16 words that were in lo, in the same order.
        for (int i = 0; i < 16; i++) {
            uint32_t got = read(1, 15 - i);
            checks++;
            if (got != first[i]) fail("T2 order", 1, 15 - i, first[i], got);
        }
    }

    void test_bypass_chain() {
        printf("T3  load hi straight from Di0 with lo bypassed; lo untouched\n");
        uint32_t lo_before[16];
        memcpy(lo_before, ref[0], sizeof lo_before);
        for (int i = 0; i < 16; i++) {
            load_hi_bypass(rnd32());
            check_all("T3");
        }
        for (int i = 0; i < 16; i++) {
            checks++;
            if (ref[0][i] != lo_before[i] || read(0, i) != lo_before[i])
                fail("T3 lo disturbed", 0, i, lo_before[i], read(0, i));
        }
    }

    void test_controls() {
        printf("T4  control checks: WE gating, single-row pulses, EN0, BYP\n");
        // WROW pulses with WE low change nothing.
        dut->di = rnd32();
        for (int k = 15; k >= 0; k--) pulse_row(k);
        check_all("T4 WE low");
        // WE high with no pulses changes nothing.
        dut->we_lo = dut->we_hi = 1; eval();
        dut->we_lo = dut->we_hi = 0; eval();
        check_all("T4 no pulse");
        // A single row pulse copies exactly one row.
        for (int m = 0; m < 2; m++) {
            for (int rep = 0; rep < 8; rep++) {
                int k = rnd(16);
                dut->di = rnd32();
                if (m == 1) { dut->a_lo = 15; dut->en_lo = 1; dut->byp_lo = 0; }
                if (m == 0) dut->we_lo = 1; else dut->we_hi = 1;
                eval();
                pulse_row(k);
                dut->we_lo = dut->we_hi = 0;
                eval();
                if (k == 0) {
                    if (m == 0) { ref[0][0] = dut->di; valid[0][0] = true; }
                    else        { ref[1][0] = ref[0][15]; valid[1][0] = valid[0][15]; }
                } else {
                    ref[m][k] = ref[m][k - 1]; valid[m][k] = valid[m][k - 1];
                }
                check_all("T4 single row");
            }
        }
        // EN0 low reads as zero; BYP passes Di0 (lo) / lo.Do0 (hi).
        for (int rep = 0; rep < 16; rep++) {
            dut->di = rnd32();
            dut->a_lo = rnd(16); dut->a_hi = rnd(16);
            dut->en_lo = 0; dut->en_hi = 0; dut->byp_lo = 0; dut->byp_hi = 0;
            eval();
            checks += 2;
            if (dut->do_lo != 0) fail("T4 EN0=0", 0, dut->a_lo, 0, dut->do_lo);
            if (dut->do_hi != 0) fail("T4 EN0=0", 1, dut->a_hi, 0, dut->do_hi);
            dut->byp_lo = 1; dut->byp_hi = 1;
            eval();
            checks += 2;
            if (dut->do_lo != dut->di) fail("T4 BYP", 0, dut->a_lo, dut->di, dut->do_lo);
            if (dut->do_hi != dut->di) fail("T4 BYP chain", 1, dut->a_hi, dut->di, dut->do_hi);
            dut->byp_lo = 0; dut->byp_hi = 0; dut->en_lo = 1; dut->en_hi = 1;
        }
        check_all("T4 after EN/BYP");
    }

    void test_random(int ops) {
        printf("T5  %d random operations against the reference model\n", ops);
        for (int i = 0; i < ops; i++) {
            switch (rnd(6)) {
            case 0: case 1: load_lo(rnd32()); break;
            case 2: load_hi_from_lo(); break;
            case 3: load_hi_bypass(rnd32()); break;
            case 4: { // random reads with WE low, including lo reads that wiggle hi.Di0
                for (int r = 0; r < 8; r++) { read(0, rnd(16)); read(1, rnd(16)); }
                break;
            }
            case 5: { // stray WROW activity with WE low must be ignored
                dut->di = rnd32();
                pulse_row(rnd(16));
                break;
            }
            }
            check_all("T5");
        }
    }
};

} // namespace

int main(int argc, char** argv) {
    auto* ctx = new VerilatedContext;
    ctx->commandArgs(argc, argv);
    ctx->randReset(2);          // random initial latch contents
    ctx->traceEverOn(true);

    uint32_t seed = 1;
    int ops = 2000;
    bool trace = false;
    for (int i = 1; i < argc; i++) {
        std::string a = argv[i];
        if (a.rfind("+seed=", 0) == 0) seed = std::strtoul(a.c_str() + 6, nullptr, 0);
        else if (a.rfind("+ops=", 0) == 0) ops = std::atoi(a.c_str() + 5);
        else if (a == "+trace") trace = true;
    }

    auto* dut = new Vtb_cfgmem_pair{ctx};
    Bench b(ctx, dut, seed);
    if (trace) {
        b.vcd = new VerilatedVcdC;
        dut->trace(b.vcd, 99);
        b.vcd->open("tb_cfgmem.vcd");
    }
    printf("CFGMEM pair testbench, seed %u\n", seed);
    b.eval();

    b.test_fill_lo();
    b.test_chain();
    b.test_bypass_chain();
    b.test_controls();
    b.test_random(ops);

    if (b.vcd) b.vcd->close();
    printf("%s: %d checks, %d errors\n", b.errors ? "FAIL" : "PASS", b.checks, b.errors);
    dut->final();
    delete dut;
    delete ctx;
    return b.errors ? 1 : 0;
}
