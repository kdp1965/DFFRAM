# CFGMEM tile trial (Tiny Tapeout CMOS5L)

A throwaway 2x2 Tiny Tapeout tile (419.52 x 313.74 um, `ihp-sg13cmos5l`) with
one `CFGMEM_IHP16` macro inside, programmed and read back through an SPI slave.
It exists to prove three things about the macro at tile level:

1. the tile's single-layer PDN (Metal4 stripes) reaches the macro's power pins,
2. tile routes can cross the macro on Metal4 and through the unused Metal3
   tracks exposed by the macro's route-through LEF,
3. the result is DRC and LVS clean with the macro's GDS merged in.

    make test-tile     # Verilator bench of the tile RTL (SPI programming)
    make tile-trial    # harden with LibreLane (needs the cmos5l PDK, see Readme)

Results land in `runs/RUN_*/final/` (GDS, LEF, DEF, metrics, a PNG render).

## Layout

The macro is 331.2 um wide, so a 1x1 tile (202.08 um) cannot hold it; 2x2 is
the smallest template on the cmos5l branch of tt-support-tools (there is no
2x1). The macro sits at (51.44, 75.6): x = 1.44 + 50 puts its Metal4 stripe
columns exactly on the tile's 50 um stripe grid (macro core offset 1.44 +
PDN offset 10 = tile core offset 2.88 + 10, modulo 50), and y is a row
boundary (20 x 3.78).

## Power

pdngen trims the tile's stripes around macros and, with no horizontal layer
in a single-layer PDN, cannot connect the macro pins. `flow.py` inserts
`Tile.ExtendPowerStripes` (`odb_stripes.py`) after `OpenROAD.GeneratePDN`: for
every hard macro it draws the tile's VPWR/VGND stripes across the macro's pin
columns from the bottom to the top of the core, warning if a column does not
coincide with a tile stripe. pdngen's own connectivity check runs before that
step and still reports the gap, so `ERROR_ON_PDN_VIOLATIONS` is off; the
IR-drop step's PSM check (after the patch) and LVS are the verdicts.

## Forcing route-through

`ROUTING_OBSTRUCTIONS` blocks Metal2 and Metal4 in the channels beside the
macro for the macro's height, so north-south routes have to cross the macro
on Metal4 (Metal3 stays open there so the macro's west-edge pins remain
reachable). Remove those entries for a plain tile.
