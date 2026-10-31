# -*- coding: utf8 -*-
# Copyright 2026 Ken Pettit
#
# This file is part of the DFFRAM Memory Compiler.
# See https://github.com/Cloud-V/DFFRAM for further info.
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
Placement for the cfgmem_gf model (CFGMEM8x44 on gf180mcu_fd_sc_mcu7t5v0):
the PRISM State Information Table of the ttboat26 TinyQV tile.

Row layout (row 0 is the bottom of the macro, next to the S-edge pins):

    row 11     spare row (TOP_SPARE_ROWS 1: DFFRAM.DiodePerNet's diodes)
    row 10     quad 1 read-out   [aoi22][aoi22] x 44
    rows 6-9   words 4..7        [and2_4] [latq_1] x 22 [diodes] [latq_1] x 22 [clkbuf_8]
    row 5      quad 0 read-out
    rows 1-4   words 0..3
    row 0      output row        [nand4] x 44

Every row is padded so that bit column i occupies the same x range in all
rows; the column pitch is the widest per-bit cell group plus a tap cell and
one antenna diode of slack, all taken from the netlist's cell widths (as the
IHP placer does).  Unlike the IHP libraries, GF180 needs tap cells, which
Row.place inserts on its own: every group is therefore placed by measuring
the cursor and padding to the group's span, so a tap the row drops in is
absorbed by the slack and never shifts a column.

The DEC3x8 decoder (common_data.Decoder3x8) follows each row's last cell:
AND1-7 after the select buffers of word rows 2-4 and 6-9, the buffers in
row 0, two inverters after word 0's select buffer in row 1, AND0 and the
other inverters with the input-pin antenna diodes in row 5.  Nothing is padded before that and no row-end
margin is kept (config.yml), so the macro is as wide as a word row plus
one and4_2.  The spare row on top is left to the fill
pass (placeram/cli.py) so DiodePerNet finds only fill there.
"""
from .row import Row
from .util import d2a
from .placeable import Placeable, DataError
from .common_data import Decoder3x8

from odb import dbInst as Instance

from typing import Dict, List

S = Placeable.Sieve


def sites(instance: Instance) -> int:
    """Width of an instance's master in (integer) sites."""
    return int(round(instance.getMaster().getWidth() / Row.sw))


def skip(r: Row, count: int):
    """Leave `count` sites of the row empty (filled later by the flow)."""
    r.x += count * Row.sw


def place_group(r: Row, cells: List[Instance], span: int, what: str):
    """Place `cells` at the row's cursor and move the cursor `span` sites past
    where it was, whatever taps the row inserted on the way."""
    x0 = r.x
    for c in cells:
        r.place(c)
    used = int(round((r.x - x0) / Row.sw))
    if used > span:
        raise DataError(
            "%s in row %i needs %i sites, column span is %i" % (what, r.ordinal, used, span)
        )
    skip(r, span - used)


class ColumnGeometry:
    """Site counts shared by every row so the bit columns line up."""

    def __init__(self, prefix: int, pitch: int, mid: int, split: int):
        self.prefix = prefix  # sites reserved at the start of every row (the row AND)
        self.pitch = pitch  # sites per bit column
        self.mid = mid  # sites of the mid-row gap (the row's diodes live here)
        self.split = split  # bit index before which the mid gap is placed


class GfCfgSlice(Placeable):
    """One configuration word: a row of latches with its row AND, select buffer and diodes."""

    def __init__(self, instances: List[Instance]):
        self.bits: Dict[int, Instance] = {}

        def process_bit(instance, bit):
            self.bits[int(bit)] = instance

        self.sieve(
            instances,
            [
                S(variable="cfg_bit", groups=["bit"], custom_behavior=process_bit),
                S(variable="cfg_diode"),
                S(variable="seldiode"),
                S(variable="selbuf"),
                S(variable="rowand"),
            ],
        )
        self.dicts_to_lists()

    def bit_width(self) -> int:
        return max(sites(b) for b in self.bits.values())

    def diodes(self) -> List[Instance]:
        return [d for d in [self.cfg_diode, self.seldiode] if d is not None]

    def place(self, row_list: List[Row], start_row: int, geo: ColumnGeometry):
        r = row_list[start_row]
        place_group(r, [self.rowand], geo.prefix, "row AND")
        for i in range(len(self.bits)):
            if i == geo.split:
                place_group(r, self.diodes(), geo.mid, "row diodes")
            place_group(r, [self.bits[i]], geo.pitch, "latch %i" % i)
        r.place(self.selbuf)
        return start_row + 1

    def word_count(self):
        return 1


class GfCfgMem_8(Placeable):
    """An 8-word configuration memory (cfgmem_gf building blocks)."""

    WORDS = 8
    WORDS_PER_QUAD = 4
    TOP_SPARE_ROWS = 0  # set by placeram/cli.py (--top-rows)
    COMPACT_DECODER = False  # set by placeram/cli.py from config.yml compact_decoder
    BALANCED_DECODER = False  # set by placeram/cli.py from config.yml balanced_decoder
    COLUMN_SLACK = 0  # empty sites per bit column beyond the tap

    def __init__(self, instances: List[Instance]):
        raw_slices: Dict[int, List[Instance]] = {}
        raw_decoders: Dict[str, List[Instance]] = {}
        quad_aoi: Dict[int, Dict[int, Dict[int, Instance]]] = {}
        out_nand: Dict[int, Instance] = {}
        a_diodes: Dict[int, Instance] = {}

        def process_slice(instance, slice):
            raw_slices.setdefault(int(slice), []).append(instance)

        def process_decoder(instance, decoder):
            raw_decoders.setdefault(decoder, []).append(instance)

        def process_quad_aoi(instance, quad, bit, idx):
            quad_aoi.setdefault(int(quad), {}).setdefault(int(bit), {})[int(idx)] = instance

        def process_out_nand(instance, bit):
            out_nand[int(bit)] = instance

        def process_a_diodes(instance, port, bit):
            a_diodes[int(bit)] = instance

        self.sieve(
            instances,
            [
                S(
                    variable="a_diodes",
                    groups=["port", "address_bit"],
                    custom_behavior=process_a_diodes,
                ),
                S(variable="in_diodes", groups=["pin"]),
                S(variable="decoders", groups=["port"], custom_behavior=process_decoder),
                S(variable="cfg_slices", groups=["slice"], custom_behavior=process_slice),
                S(variable="out_nand", groups=["bit"], custom_behavior=process_out_nand),
                S(
                    variable="quad_aoi",
                    groups=["quad", "bit", "idx"],
                    custom_behavior=process_quad_aoi,
                ),
            ],
        )
        self.dicts_to_lists()

        self.decoders = d2a({k: Decoder3x8(v) for k, v in raw_decoders.items()})
        self.slices = d2a({k: GfCfgSlice(v) for k, v in raw_slices.items()})
        if len(self.slices) != self.WORDS:
            raise DataError("GfCfgMem_8: %i word slices found, expected %i" % (len(self.slices), self.WORDS))
        # quad -> bit -> [aoi0, aoi1]
        self.quads: List[List[List[Instance]]] = []
        for q in range(len(quad_aoi)):
            bits = []
            for b in range(len(quad_aoi[q])):
                bits.append(d2a(quad_aoi[q][b]))
            self.quads.append(bits)
        self.out_cells: List[List[Instance]] = [[out_nand[b]] for b in range(len(out_nand))]
        self.a_diodes = d2a(a_diodes)
        self.pin_diodes: List[Instance] = list(self.a_diodes) + list(self.in_diodes or [])

    def geometry(self) -> ColumnGeometry:
        """Derive the shared column geometry from the actual cell widths."""
        latch = max(s.bit_width() for s in self.slices)
        quad = max(sum(sites(c) for c in cells) for q in self.quads for cells in q)
        out = max(sum(sites(c) for c in cells) for cells in self.out_cells)

        # No slack beyond the tap: the model's own diodes sit in the mid gap
        # and DFFRAM.DiodePerNet uses the spare row, the antenna repair is
        # jumper-only (config.yml), so nothing is legalised into the columns
        # later.  (The IHP placer left a diode's width per column; here that
        # was 88 sites, 49 um of the macro's width.)
        tap = int(round(Row.tap_width)) if Row.tap_width else 0  # cli.py stores it as a float
        pitch = max(latch, quad, out) + tap + self.COLUMN_SLACK

        prefix = max(sites(s.rowand) for s in self.slices) + tap
        mid = max(sum(sites(d) for d in s.diodes()) for s in self.slices) + tap
        split = len(self.out_cells) // 2
        return ColumnGeometry(prefix, pitch, mid, split)

    def place_bit_row(self, r: Row, cells_per_bit: List[List[Instance]], geo: ColumnGeometry, what: str):
        """Place one cell group per bit column, padded to the column pitch."""
        skip(r, geo.prefix)
        for i, cells in enumerate(cells_per_bit):
            if i == geo.split:
                skip(r, geo.mid)
            place_group(r, cells, geo.pitch, "%s bit %i" % (what, i))

    def place(self, row_list: List[Row], start_row: int = 0):
        geo = self.geometry()
        current_row = start_row

        # The rows come in N / FS pairs that share an n-well, and Row taps
        # the odd row of each pair at its start, the even one only after a
        # tap distance: the pair is covered at both ends.  With an odd row
        # count the top row has no partner, so its n-well gets only its own
        # taps - none in its first tap distance, where the decap fill of its
        # empty prefix holds PMOS: DF.13_MV (n-well tap within 15 um of a
        # PCOMP) failed 4 times at the left end of the 11-row macro's top
        # row on the KLayout deck (the 12-row build had the spare row of
        # filltie on top as its partner).  The unpaired row taps at its start
        # and every half tap distance.
        top = start_row + 1 + len(self.quads) * (self.WORDS_PER_QUAD + 1) - 1
        if (top - start_row + 1) % 2 == 1 and Row.tap_distance:
            r = row_list[top]
            r.tap_distance = Row.tap_distance / 2
            r.since_last_tap = r.tap_distance

        # Act 1. Output row: a NAND4 per bit.
        self.place_bit_row(row_list[current_row], self.out_cells, geo, "output")
        current_row += 1

        # Act 2. Two quads: four word rows each, then the quad's read-out row.
        for q in range(len(self.quads)):
            for w in range(self.WORDS_PER_QUAD):
                slice = self.slices[q * self.WORDS_PER_QUAD + w]
                current_row = slice.place(row_list, current_row, geo)
            self.place_bit_row(row_list[current_row], self.quads[q], geo, "quad %i" % q)
            current_row += 1

        array_rows = current_row

        # Act 3. The decoder, straight after each row's last cell, with no
        # equalising fill before it (Ken, 2026-10-29: padding the rows to the
        # word rows' width first put the buffers beyond that width in the
        # short output row and so set the macro's width; the rows are filled
        # once, at the end, by placeram/cli.py).
        out_row = row_list[start_row]
        gap_row = row_list[start_row + 1 + self.WORDS_PER_QUAD]
        if self.COMPACT_DECODER:
            # The word rows end with their select buffer; AND1-7 follow it in
            # the rows of words 1-7 (one and4_2 each, the row end of the
            # macro).  Everything else goes into the short rows' slack so no
            # row ends past that: the address and enable buffers in the output
            # row, two inverters after word 0's select buffer (that row has no
            # AND), AND0 (a nor4_2, the widest decoder gate) and the other two
            # inverters in the quad 0 row with the input pins' antenna diodes.
            # 12.88 um narrower (582.40 x 50.96 with ROW_END_MARGIN 0), but in
            # the ttboat26 tile it did not route (global routing overflow
            # 888-1017 against 395-447, 2 violations left), so it is opt-in
            # (config.yml compact_decoder).
            word0_row = row_list[start_row + 1]
            for dec in self.decoders:
                for buf in list(dec.abufs) + [dec.enbuf]:
                    out_row.place(buf)
                invs = list(dec.invs)
                for inv in invs[: len(invs) // 2]:
                    word0_row.place(inv)
                gap_row.place(dec.and_gates[0])
                for inv in invs[len(invs) // 2 :]:
                    gap_row.place(inv)
                for w in range(1, self.WORDS):
                    row = start_row + 1 + w + (1 if w >= self.WORDS_PER_QUAD else 0)
                    row_list[row].place(dec.and_gates[w])
        elif self.BALANCED_DECODER:
            # Decoder3x8's column with AND0 and the enable buffer swapped: the
            # nor4_2 (10.08 um) made word 0's row the longest, the clkbuf_2
            # (4.48 um) takes its place there and the output row, the short
            # one, takes the nor4_2.  The rows of words 0-3 then end within
            # an inverter of each other.
            for dec in self.decoders:
                for buf in dec.abufs:
                    out_row.place(buf)
                out_row.place(dec.and_gates[0])
                for w in range(self.WORDS):
                    row = row_list[start_row + 1 + w + (1 if w >= self.WORDS_PER_QUAD else 0)]
                    row.place(dec.enbuf if w == 0 else dec.and_gates[w])
                    if w < len(dec.invs):
                        row.place(dec.invs[w])
        else:
            # Decoder3x8's own column: its buffers in the output row, AND0-3
            # (and an inverter each) in the rows of words 0-3, a gap at the
            # quad 0 row, AND4-7 in the rows of words 4-7.
            for decoder in self.decoders:
                decoder.place(row_list, start_row)

        # Act 4. The input pins' antenna diodes end the quad 0 row.
        for d in self.pin_diodes:
            gap_row.place(d)

        return array_rows + self.TOP_SPARE_ROWS

    def word_count(self):
        return self.WORDS
