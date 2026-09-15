# CFGMEM16 testbench

Verilator regression for the CFGMEM16 configuration memory macros: the same
stimulus runs against the RTL models and the gate-level netlists produced by
`dffram.py`, for sky130, IHP sg13g2 and IHP sg13cmos5l.

    make -C verification/cfgmem            # from the nix shell; runs what exists
    make -C verification/cfgmem nl-cmos5l  # one target
    make test-cfgmem                       # from the repository root

Targets: `rtl-ihp`, `nl-cmos5l`, `nl-sg13g2`, `rtl-sky130`, `nl-sky130`.
The `nl-*` targets read the netlists under `products/` and are skipped by
`make all` when they have not been built. `SEED=` and `OPS=` change the random
seed and the number of random operations; `TRACE=1` writes a VCD.

## What is tested

`tb_cfgmem_pair.v` chains two macros the way the PRISM peripheral does: a
right-hand macro `lo` and a left-hand macro `hi`, with `hi.Di0 = lo.Do0` and a
shared `WROW` bus. `tb_cfgmem.cpp` keeps a reference model of the 16 words in
each macro and reads every loaded row back through the random-access port in
random order after each step. Latches start in a random state, so a row only
counts once it has been loaded.

The load protocol is the one `cfgmem_periph.v` implements: raise `WE0`, then
pulse `WROW` one-hot from row 15 down to row 0. Row k copies row k-1 and row 0
copies `Di0`, so 16 pulses shift one word in and every older word one row up.

1. Fill `lo` with 16 words, checking all rows after every load.
2. Shift the 16 words out of `lo` into `hi` through `lo` row 15 (`A0 = 15`),
   refilling `lo` each time, and check `hi` ends up with the words in order.
3. Load `hi` straight from `Di0` with `lo` bypassed (`BYP`), `lo` untouched.
4. Controls: `WROW` pulses with `WE0` low and `WE0` without pulses change
   nothing; a single-row pulse changes only that row; `EN0 = 0` reads zero;
   `BYP` passes the input through, including across the chain.
5. Random mix of the above against the reference model.

## Cell models

Verilator cannot compile the PDK cell models (they use UDP primitives), so
`models/` holds zero-delay behavioral models of the cells the macros use,
written from the liberty functions. `sg13cmos5l_cells.v` is generated from
`sg13g2_cells.v` by renaming the prefix. Deliberately broken models (read-out
mis-wired, latch polarity inverted, decoder enable ignored) all make the bench
fail, which is the check that the bench itself works.
