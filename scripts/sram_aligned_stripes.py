#!/usr/bin/env python3
# Copyright 2026 Ken Pettit
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Print a dffram.py --pdn-stripes list that puts a macro's Metal4 rails on
the supply columns of an IHP 1P SRAM it sits above (or below) in a parent.

The SRAM has three power regions: two bit-cell arrays, each a row of
VPWR/VGND column pairs (VDD at x, VSS at x + 5.62, same polarity every
11.24 um; the right array's grid is 0.67 um off the left one's), and the
periphery band between them (VDD / VSS columns 5.15 apart).  The stripes
chosen are the parent's SRAM stripe pattern:

  * every other pair of each array, phased to the pairs the parent's
    regular grid (--grid-vpwr + k * --grid-pitch) lands on;
  * the band's leftmost and rightmost VDD/VSS pair;
  * the parent's regular grid pairs wherever the macro reaches past the
    SRAM's x range.

Only the stripes inside the macro's core are printed, in macro coordinates
(x = parent x - --macro-x), SRAM columns at the SRAM's column width and
grid stripes at --grid-width.  Placements are N / FS for both (no x flip).
The table on stderr gives the parent x of each stripe.
"""

import argparse
import re
import sys
from decimal import Decimal as D


def sram_columns(lef_text):
    """[(net, centre, width, is_array)] of the Metal4 power columns."""
    cols = {}
    for m in re.finditer(r"PIN\s+(\S+)(.*?)END\s+\1", lef_text, re.S):
        name, body = m.group(1), m.group(2)
        if not re.search(r"USE\s+(POWER|GROUND)", body):
            continue
        net = "VGND" if re.search(r"USE\s+GROUND", body) else "VPWR"
        layer = None
        for line in body.splitlines():
            t = line.split()
            if not t:
                continue
            if t[0] == "LAYER":
                layer = t[1]
            if t[0] == "RECT" and layer == "Metal4":
                x0, x1 = D(t[1]), D(t[3])
                key = ((x0 + x1) / 2, net)
                c = cols.setdefault(key, {"w": x1 - x0, "array": False})
                if "ARRAY" in name.upper():
                    c["array"] = True
    return sorted((n, x, v["w"], v["array"]) for (x, n), v in cols.items())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sram-lef", required=True)
    ap.add_argument("--sram-x", type=D, required=True, help="parent x of the SRAM origin")
    ap.add_argument("--macro-x", type=D, required=True, help="parent x of the macro origin")
    ap.add_argument("--macro-width", type=D, required=True, help="macro die width (um)")
    ap.add_argument("--core-margin", type=D, default=D("1.44"), help="macro core inset from the die edges (um)")
    ap.add_argument("--grid-vpwr", type=D, default=D("9.03"), help="parent x of a regular-grid VPWR stripe")
    ap.add_argument("--grid-pitch", type=D, default=D("44.96"))
    ap.add_argument("--pair", type=D, default=D("5.62"), help="VGND offset from VPWR in a pair (um)")
    ap.add_argument("--grid-width", type=D, default=D("2.1"))
    ap.add_argument("--tol", type=D, default=D("1.0"), help="grid-to-column match tolerance (um)")
    a = ap.parse_args()

    text = open(a.sram_lef).read()
    size = re.search(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", text)
    sram_w = D(size.group(1))
    cols = sram_columns(text)

    # arrays: the VPWR columns with an array supply, split at the widest gap
    arr = sorted(x for n, x, w, is_arr in cols if is_arr and n == "VPWR")
    gap = max(range(1, len(arr)), key=lambda i: arr[i] - arr[i - 1])
    arrays = {"array L": arr[:gap], "array R": arr[gap:]}
    vss = {x for n, x, w, _ in cols if n == "VGND"}
    width = {x: w for n, x, w, _ in cols}

    def near(x, xs, tol=D("0.1")):
        return next((y for y in xs if abs(y - x) <= tol), None)

    chosen = []  # (net, parent x, width, tag)
    grid = [a.grid_vpwr + k * a.grid_pitch for k in range(-2, 200)]
    for region, vdds in arrays.items():
        pairs = [(v, near(v + a.pair, vss)) for v in vdds]
        pairs = [(k, v, g) for k, (v, g) in enumerate(pairs) if g is not None]
        held = [
            k for k, v, g in pairs if any(abs(a.sram_x + v - x) <= a.tol for x in grid)
        ]
        if not held:
            sys.exit(f"{region}: no pair is on the parent grid; check --grid-vpwr / --sram-x")
        odd = sum(k % 2 for k in held)
        phase = 1 if 2 * odd > len(held) else 0
        for k, v, g in pairs:
            if k % 2 == phase:
                chosen.append(("VPWR", a.sram_x + v, width[v], f"{region} pair {k}"))
                chosen.append(("VGND", a.sram_x + g, width[g], f"{region} pair {k}"))
        print(f"{region}: {len(pairs)} pairs, grid holds {held}, every other = parity {phase}",
              file=sys.stderr)

    lo = max(arrays["array L"]) + a.pair + D("0.1")
    hi = min(arrays["array R"]) - a.pair - D("0.1")
    band = sorted(((n, x) for n, x, w, is_arr in cols if lo < x < hi), key=lambda t: t[1])
    if len(band) < 4:
        sys.exit(f"band between the arrays has {len(band)} columns")
    for tag, two in (("band left", band[:2]), ("band right", band[-2:])):
        if two[0][0] == two[1][0]:
            sys.exit(f"{tag}: {two} is not a VPWR/VGND pair")
        for n, x in two:
            chosen.append((n, a.sram_x + x, width[x], tag))

    x0, x1 = a.sram_x, a.sram_x + sram_w
    for g in grid:
        if g + a.pair < x0 - 1 or g > x1 + 1:
            chosen.append(("VPWR", g, a.grid_width, "grid"))
            chosen.append(("VGND", g + a.pair, a.grid_width, "grid"))

    core_lo = a.core_margin
    core_hi = a.macro_width - a.core_margin
    out = []
    for n, x, w, tag in sorted(chosen, key=lambda t: t[1]):
        m = x - a.macro_x
        if m - w / 2 < core_lo or m + w / 2 > core_hi:
            continue
        out.append(f"{n}:{m.normalize():f}:{w.normalize():f}")
        print(f"  {n:4s} parent {x:9.3f}  macro {m:8.3f}  w {w}  {tag}", file=sys.stderr)
    print(f"{len(out)} stripes", file=sys.stderr)
    print(",".join(out))


if __name__ == "__main__":
    main()
