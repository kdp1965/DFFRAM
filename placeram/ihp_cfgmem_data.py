# -*- coding: utf8 -*-
# Copyright ©2020-2022 The American University in Cairo
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
Placement for the cfgmem_ihp / cfgmem_ihp_left models (IHP sg13g2).

Unlike the sky130 CfgMem_16 placer, nothing here assumes cell widths: every
column pitch and every alignment gap is derived from the widths of the cells
actually in the netlist, so it adapts if a cell is swapped for a different
drive strength.

Row layout (row 0 is the bottom of the macro, next to the S-edge Di0/Do0 pins):

    row 20   quad 3 read-out   [a22oi][a22oi][and2] x 32
    rows 16-19 words 12..15    [and2_2] [dlhq_1] x 16 [diodes] [dlhq_1] x 16 [buf_4]
    row 15   quad 2 read-out
    rows 11-14 words 8..11
    row 10   quad 1 read-out
    rows 6-9   words 4..7
    row 5    quad 0 read-out
    rows 1-4   words 0..3
    row 0    output row        [nand4][mux2] x 32

Every row is padded so that bit column i occupies the same x range in all
rows. Padding inside the array is left as empty gaps (one antenna diode wide
per bit column) rather than filled: the antenna-repair and diode-insertion
steps later in the flow need that slack to legalise the diodes they add, and
OpenROAD.FillInsertion closes whatever remains. The address decoder, address
buffers and bypass buffer form a column to the right of the array.
"""
from .row import Row
from .util import d2a
from .placeable import Placeable
from .common_data import Decoder4x16

from odb import dbInst as Instance

from typing import Dict, List

S = Placeable.Sieve


def sites(instance: Instance) -> int:
    """Width of an instance's master in (integer) sites."""
    return int(round(instance.getMaster().getWidth() / Row.sw))


def skip(r: Row, count: int):
    """Leave `count` sites of the row empty (filled later by the flow)."""
    r.x += count * Row.sw


class ColumnGeometry:
    """Site counts shared by every row so the bit columns line up."""

    def __init__(self, prefix: int, pitch: int, mid: int, split: int, slack: int):
        self.prefix = prefix  # sites reserved at the start of every row
        self.pitch = pitch  # sites per bit column (widest cell group + slack)
        self.mid = mid  # sites of the mid-row gap (diodes live here)
        self.split = split  # bit index before which the mid gap is placed
        self.slack = slack  # empty sites left in every bit column


class IhpCfgSlice(Placeable):
    """One 32-bit configuration word (one row of latches)."""

    def __init__(self, instances: List[Instance], left: bool):
        self.left = left
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

    def mid_width(self) -> int:
        return sum(sites(d) for d in [self.cfg_diode, self.seldiode] if d is not None)

    def place(self, row_list: List[Row], start_row: int, geo: ColumnGeometry):
        r = row_list[start_row]

        # Row enable AND: at the west end for the normal macro (WE/WROW pins
        # on the W edge) and at the east end for the left-hand macro.
        if self.left:
            skip(r, geo.prefix)
        else:
            r.place(self.rowand)
            skip(r, geo.prefix - sites(self.rowand))

        for i in range(len(self.bits)):
            if i == geo.split:
                used = 0
                for d in [self.cfg_diode, self.seldiode]:
                    if d is not None:
                        r.place(d)
                        used += sites(d)
                skip(r, geo.mid - used)
            bit = self.bits[i]
            r.place(bit)
            skip(r, geo.pitch - sites(bit))

        r.place(self.selbuf)
        if self.left:
            r.place(self.rowand)

        return start_row + 1

    def word_count(self):
        return 1


class IhpCfgMem_16(Placeable):
    """A 16-word x 32-bit configuration memory (cfgmem_ihp building blocks)."""

    WORDS = 16
    WORDS_PER_QUAD = 4

    def __init__(self, instances: List[Instance], left: bool):
        self.left = left
        raw_slices: Dict[int, List[Instance]] = {}
        raw_decoders: Dict[str, List[Instance]] = {}
        quad_a22oi: Dict[int, Dict[int, Dict[int, Instance]]] = {}
        quad_and: Dict[int, Dict[int, Instance]] = {}
        out_nand: Dict[int, Instance] = {}
        out_mux: Dict[int, Instance] = {}
        abufs: Dict[int, Instance] = {}
        a_diodes: Dict[int, Instance] = {}

        def process_slice(instance, slice):
            raw_slices.setdefault(int(slice), []).append(instance)

        def process_decoder(instance, decoder):
            raw_decoders.setdefault(decoder, []).append(instance)

        def process_quad_a22oi(instance, quad, bit, idx):
            quad_a22oi.setdefault(int(quad), {}).setdefault(int(bit), {})[
                int(idx)
            ] = instance

        def process_quad_and(instance, quad, bit):
            quad_and.setdefault(int(quad), {})[int(bit)] = instance

        def process_out_nand(instance, bit):
            out_nand[int(bit)] = instance

        def process_out_mux(instance, bit):
            out_mux[int(bit)] = instance

        def process_abufs(instance, port, bit):
            abufs[int(bit)] = instance

        def process_a_diodes(instance, port, bit):
            a_diodes[int(bit)] = instance

        self.sieve(
            instances,
            [
                S(variable="bypbuf"),
                S(
                    variable="a_diodes",
                    groups=["port", "address_bit"],
                    custom_behavior=process_a_diodes,
                ),
                S(
                    variable="abufs",
                    groups=["port", "address_bit"],
                    custom_behavior=process_abufs,
                ),
                S(variable="decoders", groups=["port"], custom_behavior=process_decoder),
                S(variable="cfg_slices", groups=["slice"], custom_behavior=process_slice),
                S(variable="out_nand", groups=["bit"], custom_behavior=process_out_nand),
                S(variable="out_mux", groups=["bit"], custom_behavior=process_out_mux),
                S(
                    variable="quad_a22oi",
                    groups=["quad", "bit", "idx"],
                    custom_behavior=process_quad_a22oi,
                ),
                S(
                    variable="quad_and",
                    groups=["quad", "bit"],
                    custom_behavior=process_quad_and,
                ),
            ],
        )
        self.dicts_to_lists()

        self.decoders = d2a({k: Decoder4x16(v) for k, v in raw_decoders.items()})
        self.slices = d2a({k: IhpCfgSlice(v, left) for k, v in raw_slices.items()})
        # quad -> bit -> [a22oi0, a22oi1, and2]
        self.quads: List[List[List[Instance]]] = []
        for q in range(len(quad_and)):
            bits = []
            for b in range(len(quad_and[q])):
                bits.append(d2a(quad_a22oi[q][b]) + [quad_and[q][b]])
            self.quads.append(bits)
        self.out_cells: List[List[Instance]] = [
            [out_nand[b], out_mux[b]] for b in range(len(out_nand))
        ]
        self.abufs = d2a(abufs)
        self.a_diodes = d2a(a_diodes)

    def geometry(self) -> ColumnGeometry:
        """Derive the shared column geometry from the actual cell widths."""
        latch = max(s.bit_width() for s in self.slices)
        quad = max(sum(sites(c) for c in cells) for q in self.quads for cells in q)
        out = max(sum(sites(c) for c in cells) for cells in self.out_cells)

        # One antenna diode of slack per column, so the diode insertion and
        # antenna repair steps can legalise a diode next to any bit.
        diodes = [
            d
            for s in self.slices
            for d in (s.cfg_diode, s.seldiode)
            if d is not None
        ]
        slack = max(sites(d) for d in diodes) if diodes else 2
        pitch = max(latch, quad, out) + slack

        prefix = 0 if self.left else max(sites(s.rowand) for s in self.slices)
        mid = max(s.mid_width() for s in self.slices)
        split = len(self.out_cells) // 2
        return ColumnGeometry(prefix, pitch, mid, split, slack)

    def place_bit_row(
        self, r: Row, row_idx: int, cells_per_bit: List[List[Instance]], geo: ColumnGeometry
    ):
        """Place one cell group per bit column, padded to the column pitch."""
        skip(r, geo.prefix)
        for i, cells in enumerate(cells_per_bit):
            if i == geo.split:
                skip(r, geo.mid)
            used = 0
            for c in cells:
                r.place(c)
                used += sites(c)
            skip(r, geo.pitch - used)

    def place(self, row_list: List[Row], start_row: int = 0):
        geo = self.geometry()
        current_row = start_row

        # Act 1. Output row: NAND4 + bypass MUX per bit.
        self.place_bit_row(row_list[current_row], current_row, self.out_cells, geo)
        current_row += 1

        # Act 2. Four quads: four word rows each, then the quad read-out row.
        for q in range(len(self.quads)):
            for w in range(self.WORDS_PER_QUAD):
                slice = self.slices[q * self.WORDS_PER_QUAD + w]
                current_row = slice.place(row_list, current_row, geo)
            self.place_bit_row(row_list[current_row], current_row, self.quads[q], geo)
            current_row += 1

        array_rows = current_row

        # Equalise the array rows so the decoder column starts at one x.
        Row.fill_rows(row_list, start_row, array_rows)

        # Act 3. Decoder column to the right of the array.
        for decoder in self.decoders:
            decoder.place(row_list, start_row)

        # Act 4. Bypass buffer next to the muxes it drives; address buffers and
        # their diodes on the rows above it.
        row_list[start_row].place(self.bypbuf)
        for i, (buf, diode) in enumerate(zip(self.abufs, self.a_diodes)):
            r = row_list[start_row + 1 + i]
            r.place(buf)
            r.place(diode)

        return array_rows

    def word_count(self):
        return self.WORDS
