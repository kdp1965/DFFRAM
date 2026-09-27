# -*- coding: utf8 -*-
# Copyright 2026 Ken Pettit
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Placement for the lram_ihp model: LRAM_IHP16x8, sixteen words of eight
latches with a clocked write port and an asynchronous read port.

The bits are stacked (one standard-cell row per bit) and the words run
across, so a word's gated clock and read select are short vertical nets
and a bit's data-in and read-out nets stay inside its row.  Ten rows, row 0
at the bottom (the pins: models/lram_ihp/pin_order.cfg, now every pin on
the S edge spread across the width and moved to Metal4; the rows below are
unchanged from the E-edge-pin first version):

    row 9    select row   [WSEL w0][ ][WSEL w1][RSEL w0][RSEL w1][ ]  per pair,
                          the two predecoders filling the gaps from the east
    rows 1-8 bit rows     [latch w0][latch w1][a22oi][slack]  per pair,
                          [and2] after every second pair, then
                          [nand4][Do buf][Di buf][reset buf]
    row 0    clock row    [lgcp w0][lgcp w1][ ]  per pair, then
                          [CLK inverter][reset root buffer]

Column positions are derived from the cell widths in the netlist, as in
the CFGMEM placer, and shared by all rows so word w's latches, clock gate
and selects line up.  The slack after each pair is one antenna diode wide,
for the diode insertion / antenna repair steps to legalise into.

With --left (models/lram_ihp_left, LRAM_IHP_LEFT16x8, every pin on the W
edge) the same layout is mirrored: word 0 at the east end, the tails and
the predecoders at the west end next to the pins.  Only the positions
mirror, the cells keep their row orientation, and the power rails do not
move (they come from the PDN step's offset, not from the placement).
"""
from .row import Row
from .placeable import Placeable

from odb import dbInst as Instance

from typing import Dict, List, Tuple

S = Placeable.Sieve


def sites(instance: Instance) -> int:
    """Width of an instance's master in (integer) sites."""
    return int(round(instance.getMaster().getWidth() / Row.sw))


def skip(r: Row, count: int):
    """Leave `count` sites of the row empty (filled later by the flow)."""
    r.x += count * Row.sw


class IhpLatchRam(Placeable):
    """A 16-word x 8-bit latch RAM (lram_ihp building blocks)."""

    WORDS = 16
    SLACK = 3  # empty sites after every word pair (one sg13 antenna diode)

    def __init__(self, instances: List[Instance], left: bool = False):
        self.left = left
        store: Dict[int, Dict[int, Instance]] = {}
        cg: Dict[int, Instance] = {}
        wsel: Dict[int, Instance] = {}
        rsel: Dict[int, Instance] = {}
        pair: Dict[int, Dict[int, Instance]] = {}
        quad: Dict[int, Dict[int, Instance]] = {}
        onand: Dict[int, Instance] = {}
        dobuf: Dict[int, Instance] = {}
        dibuf: Dict[int, Instance] = {}
        rstbuf: Dict[int, Instance] = {}
        misc: List[Instance] = []

        def two(d):
            return lambda inst, a, b: d.setdefault(int(a), {}).__setitem__(int(b), inst)

        def one(d):
            return lambda inst, a: d.__setitem__(int(a), inst)

        def collect(inst, *_):
            misc.append(inst)

        self.sieve(
            instances,
            [
                S(variable="store", groups=["word", "bit"], custom_behavior=two(store)),
                S(variable="cg", groups=["word"], custom_behavior=one(cg)),
                S(variable="wsel", groups=["word"], custom_behavior=one(wsel)),
                S(variable="rsel", groups=["word"], custom_behavior=one(rsel)),
                S(variable="pair", groups=["bit", "pair"], custom_behavior=two(pair)),
                S(variable="quad", groups=["bit", "quad"], custom_behavior=two(quad)),
                S(variable="onand", groups=["bit"], custom_behavior=one(onand)),
                S(variable="dobuf", groups=["bit"], custom_behavior=one(dobuf)),
                S(variable="dibuf", groups=["bit"], custom_behavior=one(dibuf)),
                S(variable="rstbuf", groups=["bit"], custom_behavior=one(rstbuf)),
                S(variable="clkinv"),
                S(variable="rstroot"),
                S(variable="wdec", groups=["cell"], custom_behavior=collect),
                S(variable="rdec", groups=["cell"], custom_behavior=collect),
            ],
        )
        # the sieve also filled string-keyed deep dictionaries; keep the
        # integer-keyed ones built above (d2a would sort "10" before "2")
        self.store = store
        self.cg = cg
        self.wsel = wsel
        self.rsel = rsel
        self.pair = pair
        self.quad = quad
        self.onand = onand
        self.dobuf = dobuf
        self.dibuf = dibuf
        self.rstbuf = rstbuf
        self.misc = misc

        self.words = len(self.cg)
        self.bits = len(self.onand)
        if self.words != self.WORDS:
            raise ValueError(f"expected {self.WORDS} words, found {self.words} clock gates")
        for w in range(self.words):
            if len(self.store[w]) != self.bits:
                raise ValueError(f"word {w} has {len(self.store[w])} latches, expected {self.bits}")

    # ---- geometry --------------------------------------------------------

    def geometry(self):
        L = max(sites(i) for w in self.store.values() for i in w.values())
        CG = max(sites(i) for i in self.cg.values())
        A = max(sites(i) for r in self.pair.values() for i in r.values())
        Q = max(sites(i) for r in self.quad.values() for i in r.values())
        N = max(sites(i) for i in self.onand.values())
        SEL = max(sites(i) for i in list(self.wsel.values()) + list(self.rsel.values()))
        word = max(L, CG)  # word pitch: the latch or the clock gate, whichever is wider
        pair_w = 2 * word + A + self.SLACK
        if 3 * SEL > word + A + self.SLACK:
            raise ValueError("the select gates of a pair do not fit beside its second word")
        tail = max(
            sum(sites(c) for c in (self.dobuf[b], self.dibuf[b], self.rstbuf[b]))
            for b in range(self.bits)
        )

        pairs = self.words // 2
        quads = pairs // 2

        def pair_x(p: int) -> int:
            return p * pair_w + (p // 2) * Q

        def word_x(w: int) -> int:
            return pair_x(w // 2) + (w % 2) * word

        def a22oi_x(p: int) -> int:
            return pair_x(p) + 2 * word

        def quad_x(k: int) -> int:
            return pair_x(2 * k + 2) - Q

        body = pairs * pair_w + quads * Q
        onand_x = body
        tail_x = body + N
        return dict(
            word=word, pair_w=pair_w, sel=SEL, tail=tail,
            pair_x=pair_x, word_x=word_x, a22oi_x=a22oi_x, quad_x=quad_x,
            onand_x=onand_x, tail_x=tail_x, quads=quads, pairs=pairs,
        )

    # ---- row helpers -----------------------------------------------------

    @staticmethod
    def place_items(r: Row, items: List[Tuple[int, Instance]]) -> int:
        """Place (site, instance) pairs left to right, skipping the gaps.
        Returns the row's end in sites."""
        cur = 0
        for x, inst in sorted(items, key=lambda t: t[0]):
            if x < cur:
                raise ValueError(
                    f"{inst.getName()} at site {x} overlaps the cell ending at {cur}"
                )
            if x > cur:
                skip(r, x - cur)
            r.place(inst)
            cur = x + sites(inst)
        return cur

    @staticmethod
    def fill_gaps(
        items: List[Tuple[int, Instance]], cells: List[Instance], end: int
    ) -> List[Tuple[int, Instance]]:
        """Drop `cells` into the gaps between `items` (and the tail up to
        `end`), starting from the east so they sit near the pins; whatever
        does not fit is appended after `end`.  First fit decreasing."""
        items = sorted(items, key=lambda t: t[0])
        gaps = []
        cur = 0
        for x, inst in items:
            if x > cur:
                gaps.append((cur, x))
            cur = x + sites(inst)
        if end > cur:
            gaps.append((cur, end))
        remaining = sorted(cells, key=sites, reverse=True)
        placed = []
        for g0, g1 in sorted(gaps, key=lambda g: g[0], reverse=True):
            x = g0
            for c in list(remaining):
                if x + sites(c) <= g1:
                    placed.append((x, c))
                    x += sites(c)
                    remaining.remove(c)
        x = max(end, cur)
        for c in remaining:
            placed.append((x, c))
            x += sites(c)
        return items + placed

    # ---- placement -------------------------------------------------------

    def place(self, row_list: List[Row], start_row: int = 0):
        g = self.geometry()
        rows_used = self.bits + 2
        plan: List[List[Tuple[int, Instance]]] = []  # per row: (site, instance)

        # Row 0: the clock gates under their words, the clock inverter and
        # the reset root buffer in the tail.
        items = [(g["word_x"](w), self.cg[w]) for w in range(self.words)]
        x = g["tail_x"]
        for c in (self.clkinv, self.rstroot):
            items.append((x, c))
            x += sites(c)
        plan.append(items)

        # Rows 1..bits: one bit per row.
        for b in range(self.bits):
            items = [(g["word_x"](w), self.store[w][b]) for w in range(self.words)]
            items += [(g["a22oi_x"](p), self.pair[b][p]) for p in range(g["pairs"])]
            items += [(g["quad_x"](k), self.quad[b][k]) for k in range(g["quads"])]
            items.append((g["onand_x"], self.onand[b]))
            x = g["tail_x"]
            for c in (self.dobuf[b], self.dibuf[b], self.rstbuf[b]):
                items.append((x, c))
                x += sites(c)
            plan.append(items)

        # Top row: the write selects over their clock gates, the read selects
        # beside the pair's second word (under nothing in particular: their
        # outputs drop to the a22oi inputs of every bit row), the
        # predecoders in the gaps nearest the tail (the pin side).
        items = []
        for w in range(self.words):
            items.append((g["word_x"](w), self.wsel[w]))
        for p in range(g["pairs"]):
            x = g["word_x"](2 * p + 1) + g["sel"]
            items.append((x, self.rsel[2 * p]))
            items.append((x + g["sel"], self.rsel[2 * p + 1]))
        plan.append(self.fill_gaps(items, self.misc, g["tail_x"] + g["tail"]))

        # West-pin variant: mirror every row about the widest row's end, so
        # the tails and the predecoders sit at the west end.  Every row has
        # a cell at site 0 (word 0's gate, latch or select), so every row
        # still ends at the same x.
        if self.left:
            width = max(x + sites(inst) for items in plan for x, inst in items)
            plan = [[(width - x - sites(inst), inst) for x, inst in items] for items in plan]

        for r, items in enumerate(plan):
            self.place_items(row_list[start_row + r], items)

        Row.fill_rows(row_list, start_row, start_row + rows_used)
        return start_row + rows_used

    def word_count(self):
        return self.words
