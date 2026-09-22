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
from .util import d2a
from .row import Row
from .placeable import Placeable, DataError
from .common_data import Decoder3x8, Mux, Decoder4x16
import sys

from odb import dbInst as Instance

import math
from typing import Callable, List, Dict, Union
from itertools import zip_longest

# --

P = Placeable
S = Placeable.Sieve

class CfgSlice(Placeable):  # A slice is defined as 16 words
    def __init__(self, instances: List[Instance], left):
        self.bits = {}
        self.left = left

        def process_word(instance, bit):
            bit = int(bit[:-1]) 
            self.bits[bit] = instance

        raw_decoders: Dict[int, List[Instance]] = {}

        def process_decoder(instance, decoder):
            raw_decoders[decoder] = raw_decoders.get(decoder) or []
            raw_decoders[decoder].append(instance)

        self.sieve(
            instances,
            [
                S(variable="cfg_bit", groups=["bit"], custom_behavior=process_word),
                S(variable="cfg_diode"),
                S(variable="seldiode"),
                S(variable="selbuf"),
                S(variable="rowand"),
            ],
        )

        self.dicts_to_lists()

        self.decoders = d2a({k: Decoder3x8(v) for k, v in raw_decoders.items()})

        debug_print = False
        if debug_print:
            print(f'CfgSlice bits = {len(self.bits)}')
            print(f'CfgSlice:')
            for i in range(32):
                print(f'    {self.bits[i]}')
            print(f'    {self.cfg_diode}')
            print(f'    {self.seldiode}')
            print(f'    {self.selbuf}')

    def add_fill(self, r: Row, current_row: int, size: int):
        for i, f in enumerate(Row.supported_fill_sizes):
            while size >= f:
#                fill = Row.make_fill(current_row, r.fill_counter, i)
#                r.place(fill)
#                r.fill_counter += 1
                r.x += size * 460
                size -= f
        
    def place(self, row_list: List[Row], start_row: int = 0):
        """
        Decoders for odd addressing ports are placed on the left,
        and for even addressing ports are placed on the right.

        This is to avoid congestion.
        """
        # Act 1. Place row AND used for WE latch
        r = row_list[start_row]
        self.add_fill(r, start_row, 2)
        if not self.left:
            r.place(self.rowand)

        # Act 2. Place Slice registers
        count = len(self.bits)
        for i in range(count):
            if i == count // 2:
               r.place(self.cfg_diode)
               r.place(self.seldiode)

            r.place(self.bits[i])
            self.add_fill(r, start_row, 2)
        r.place(self.selbuf)

        if self.left:
            r.place(self.rowand)

        return start_row + 1


    def word_count(self):
        return 8

class CfgMem_16(Placeable):  # A CfgMem_16 is a 32x16 CFGMEM
    def __init__(self, instances: List[Instance], left):
        self.left = left
        raw_slices: Dict[int, List[Instance]] = {}
        self.onehot: Dict[int, List[Instance]] = {}
        quad_a21boi: Dict[int, Dict[int, Instance]] = {}
        quad_a222oi: Dict[int, Dict[int, Instance]] = {}
        raw_decoders: Dict[int, List[Instance]] = {}
        out_nands: Dict[int, Instance] = {}
        out_muxs: Dict[int, Instance] = {}
        abufs: Dict[int, Instance] = {}
        a_diodes: Dict[int, Instance] = {}

        def process_slice(instance, slice):
            slice = int(slice)
            raw_slices[slice] = raw_slices.get(slice) or []
            raw_slices[slice].append(instance)

        def process_onehot(instance, slice):
            slice = int(slice)
            self.onehot[slice] = self.onehot.get(slice) or []
            self.onehot[slice].append(instance)

        def process_quad_a21boi(instance, quad, bit):
            quad = int(quad)
            bit  = int(bit)
            quad_a21boi[quad] = quad_a21boi.get(quad) or {}
            quad_a21boi[quad][bit] = instance

        def process_quad_a222oi(instance, quad, bit):
            quad = int(quad)
            bit  = int(bit)
            quad_a222oi[quad] = quad_a222oi.get(quad) or {}
            quad_a222oi[quad][bit] = instance

        def process_out_nand(instance, bit):
            bit  = int(bit)
            out_nands[bit] = instance

        def process_out_mux(instance, bit):
            bit  = int(bit)
            out_muxs[bit] = instance

        def process_abufs(instance, port, bit):
            bit  = int(bit)
            print(f'Adding abuf {bit}, port={port}')
            abufs[bit] = instance

        def process_a_diodes(instance, port, bit):
            bit  = int(bit)
            a_diodes[bit] = instance

        def process_decoder(instance, decoder):
            raw_decoders[decoder] = raw_decoders.get(decoder) or []
            raw_decoders[decoder].append(instance)

        self.sieve(
            instances,
            [
                S(variable="clk_diode"),
#                S(variable="clkbuf"),
                S(variable="bypbuf"),
                S(variable="a_diodes", groups=["port", "address_bit"], custom_behavior=process_a_diodes),
                S(variable="abufs", groups=["port", "address_bit"], custom_behavior=process_abufs),
                S(variable="decoders", groups=["port"], custom_behavior=process_decoder),
                S(variable="cfg_slices", groups=["slice"], custom_behavior=process_slice),
#                S(variable="onehot_bit", groups=["slice"], custom_behavior=process_onehot),
#                S(variable="onehot_gclk", groups=["slice"], custom_behavior=process_onehot),
#                S(variable="onehot_and", groups=["slice"], custom_behavior=process_onehot),
                S(variable="out_nand", groups=["bit"], custom_behavior=process_out_nand),
                S(variable="out_mux", groups=["bit"], custom_behavior=process_out_mux),
                S(variable="quad_a21boi", groups=["quad", "bit"], custom_behavior=process_quad_a21boi),
                S(variable="quad_a222oi", groups=["quad", "bit"], custom_behavior=process_quad_a222oi),
#                S(variable="we_edge"),
#                S(variable="we_p2"),
            ],
        )

        self.dicts_to_lists()

        self.decoders = d2a({k: Decoder4x16(v) for k, v in raw_decoders.items()})
        self.quad_a222oi = quad_a222oi
        self.quad_a21boi = quad_a21boi
        self.out_nand = out_nands
        self.out_mux = out_muxs
        self.abufs = abufs
        self.a_diodes = a_diodes

        self.slices = d2a({k: CfgSlice(v, self.left) for k, v in raw_slices.items()})

    def add_fill(self, r: Row, current_row: int, size: int):
        for i, f in enumerate(Row.supported_fill_sizes):
            while size >= f:
                fill = Row.make_fill(current_row, r.fill_counter, i)
                r.place(fill)
                r.fill_counter += 1
                size -= f
        
    def fill_onehot(self, row: Row, current_row: int):
        # Row zero starts with decap / fill cells to match the other Slice row
        # onehot_bit and onehot_gclk widths
        self.add_fill(row, current_row, 7)

    def place(self, row_list: List[Row], start_row: int = 0):
        final_rows = []

        current_row = start_row
        r = row_list[current_row]

        # Act 1. Place Row 0 output NAND4 instances
        self.fill_onehot(r, current_row)
        self.add_fill(r, current_row, 2)
        for i in range(32):
           r.place(self.out_nand[i])   
           r.place(self.out_mux[i])   
           if i == 15:
              self.add_fill(r, current_row, 2)
#           if i == 15:
#              self.add_fill(r, current_row, 6)
#           else:
#              self.add_fill(r, current_row, 4)

        current_row += 1
        r = row_list[current_row]
        final_rows.append(current_row)

        # Act 2. Place quad groups of onehot shift, output A222OI and 4 storage rows
        for quad in range(4):

            # Place left-hand onehot bits and gclk instances
            for s in range(4):
                r = row_list[current_row]
#                # Place the onehot latch flops and clk gates
#                r.place(self.onehot[quad*4 + s][0])
#                r.place(self.onehot[quad*4 + s][1])

                # Place the storage cells
                slice = self.slices[quad * 4 + s]
                current_row = slice.place(row_list, current_row) 

            # Place filler for ROW_AND
            r = row_list[current_row]
            self.fill_onehot(r, current_row)

            for b in range(32):
                if b == 16:
                    self.add_fill(r, current_row, 2)

                # Place the A222OI and A21BOI cells
                r.place(self.quad_a222oi[quad][b])
                r.place(self.quad_a21boi[quad][b])

            current_row += 1

        sys.stdout.flush()

        final_rows.append(current_row)

        # Act 3. Place Right Vertical Elements
        current_row = start_row + 2
        for decoder in self.decoders:
            decoder.place(row_list, current_row)
            current_row += 10
        
        r = row_list[10]
        r.place(self.bypbuf)

        # Act 4.  Place A buffers and diodes
        buf_row = 2
        for i in range(4):
            r = row_list[buf_row]
            r.place(self.abufs[i])
            r.place(self.a_diodes[i])
            if i == 0:
                buf_row += 2
            elif i == 1:
                buf_row += 1

        # Row.fill_rows(row_list, start_row, current_row)
        final_rows.append(current_row)

        # Epilogue
        max_row = max(*final_rows)
        return max_row

    def word_count(self):
        return 16


class Bit(Placeable):
    def __init__(self, instances: List[Instance]):
        self.sieve(
            instances,
            [
                S(variable="store"),
                S(variable="obufs", groups=["port"]),
                S(variable="invs", groups=["port"]),
            ],
        )

        self.dicts_to_lists()

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]

        r.place(self.store)
        if len(self.invs) != 0:
            for inv in self.invs:
                r.place(inv)
        for obuf in self.obufs:
            r.place(obuf)

        return start_row


class Byte(Placeable):
    def __init__(self, instances: List[Instance]):
        raw_bits: Dict[int, List[Instance]] = {}

        def process_bit(instance, bit):
            raw_bits[bit] = raw_bits.get(bit) or []
            raw_bits[bit].append(instance)

        self.sieve(
            instances,
            [
                S(variable="bits", groups=["bit"], custom_behavior=process_bit),
                S(variable="clockgate"),
                S(variable="cgand"),
                S(variable="clkinv"),
                S(variable="clkdiode"),
                S(variable="selinvs", groups=["line"]),
            ],
        )

        self.dicts_to_lists()
        self.bits = d2a({k: Bit(v) for k, v in raw_bits.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]

        for bit in self.bits:
            bit.place(row_list, start_row)

        r.place(self.clockgate)
        r.place(self.cgand)
        r.place(self.clkdiode)
        for selinv in self.selinvs:
            r.place(selinv)
        if self.clkinv is not None:
            r.place(self.clkinv)

        return start_row


class Word(Placeable):
    def __init__(self, instances: List[Instance]):
        raw_bytes: Dict[int, List[Instance]] = {}

        def process_byte(instance, byte):
            raw_bytes[byte] = raw_bytes.get(byte) or []
            raw_bytes[byte].append(instance)

        self.sieve(
            instances,
            [
                S(variable="bytes", groups=["byte"], custom_behavior=process_byte),
                S(variable="clkbuf"),
                S(variable="selbufs", groups=["port"]),
            ],
        )

        self.dicts_to_lists()
        self.bytes = d2a({k: Byte(v) for k, v in raw_bytes.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]

        for byte in self.bytes:
            byte.place(row_list, start_row)

        r.place(self.clkbuf)
        for selbuf in self.selbufs:
            r.place(selbuf)

        return start_row + 1

    def word_count(self):
        return 1


class Slice(Placeable):  # A slice is defined as 8 words.
    def __init__(self, instances: List[Instance]):
        raw_words: Dict[int, List[Instance]] = {}

        def process_word(instance, word):
            raw_words[word] = raw_words.get(word) or []
            raw_words[word].append(instance)

        raw_decoders: Dict[int, List[Instance]] = {}

        def process_decoder(instance, decoder):
            raw_decoders[decoder] = raw_decoders.get(decoder) or []
            raw_decoders[decoder].append(instance)

        self.sieve(
            instances,
            [
                S(variable="words", groups=["word"], custom_behavior=process_word),
                S(
                    variable="decoders",
                    groups=["port"],
                    custom_behavior=process_decoder,
                ),
                S(variable="clkbuf"),
                S(variable="webufs", groups=["line"]),
                S(variable="tiezero"),
            ],
        )

        self.dicts_to_lists()

        self.decoders = d2a({k: Decoder3x8(v) for k, v in raw_decoders.items()})
        self.words = d2a({k: Word(v) for k, v in raw_words.items()})

        word_count = len(self.words)
        if word_count != 8:
            raise DataError("Slice has (%i/8) words." % word_count)

    def place(self, row_list: List[Row], start_row: int = 0):
        """
        Decoders for odd addressing ports are placed on the left,
        and for even addressing ports are placed on the right.

        This is to avoid congestion.
        """
        # Prologue. Split vertical elements into left and right columns
        vertical_left = []
        vertical_right = []
        right = True

        for decoder in self.decoders:
            target = vertical_right if right else vertical_left
            target.append(decoder)
            right = not right

        final_rows = []

        # Act 1. Place Left Vertical Elements
        current_row = start_row
        for decoder in vertical_left:
            current_row = decoder.place(row_list, start_row)

        final_rows.append(current_row)

        # Act 2. Place Horizontal Elements
        current_row = start_row
        for word in self.words:
            current_row = word.place(row_list, current_row)

        Row.fill_rows(row_list, start_row, current_row)

        place_clkbuf_alone = False
        last_column = [*self.webufs]
        if len(last_column) == 8:
            place_clkbuf_alone = True
        else:
            last_column.append(self.clkbuf)

        while len(last_column) < 8:
            last_column.append(None)

        for i in range(8):
            r = row_list[start_row + i]
            if last_column[i] is not None:
                r.place(last_column[i])

        if self.tiezero is not None:
            r.place(self.tiezero)

        if place_clkbuf_alone:
            row_list[start_row].place(self.clkbuf)

        Row.fill_rows(row_list, start_row, current_row)

        final_rows.append(current_row)

        # Act 3. Place Right Vertical Elements
        current_row = start_row
        for decoder in vertical_right:
            current_row = decoder.place(row_list, start_row)

        # Row.fill_rows(row_list, start_row, current_row)
        final_rows.append(current_row)

        # Epilogue
        max_row = max(*final_rows)
        # Row.fill_rows(row_list, start_row, max_row)
        return max_row

    def word_count(self):
        return 8



class Outreg(Placeable):
    def __init__(self, instances: List[Instance]):
        self.sieve(
            instances,
            [
                S(variable="root_clkbuf"),
                S(variable="clkbufs", groups=["byte"]),
                S(variable="ffs", groups=["byte", "bit"]),
                S(variable="diodes", groups=["byte", "bit"]),
            ],
        )

        self.dicts_to_lists()

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]

        r.place(self.root_clkbuf)
        for clkbuf, ffs, diodes in zip(self.clkbufs, self.ffs, self.diodes):
            r.place(clkbuf)
            for ff, diode in zip(ffs, diodes):
                r.place(ff)
                r.place(diode)


class LRPlaceable(Placeable):
    """
    A Placeable that can have some of its elements placed in left & right columns.

    This is to make the design more routable.
    """

    def lrplace(
        self,
        row_list: List[Row],
        start_row: int,
        addresses: int,
        common: List[Instance],
        port_elements: List[str],
        place_horizontal_elements: Callable,
    ) -> int:
        # Prologue. Split vertical elements into left and right columns
        chunks = []
        common = list(filter(lambda x: x, common))
        chunk_count = math.ceil(addresses / 2)
        per_chunk = math.ceil(len(common) / chunk_count)

        i = 0
        while i < len(common):
            chunks.append(common[i : i + per_chunk])
            i += per_chunk

        vertical_left = []
        vertical_right = []
        right = True

        for i in range(0, addresses):
            target = vertical_right if right else vertical_left
            column = []
            for accessor in port_elements:
                elements: Union[List[Instance], Instance] = getattr(self, accessor)
                if len(elements) == 0:
                    continue
                element = elements[i]
                if isinstance(element, list):
                    column += element
                else:
                    column.append(element)
            if right and len(chunks):
                column += chunks[i // 2]
            target.append(column)
            right = not right

        final_rows = []

        # Act 1. Place Left Vertical Elements
        current_row = start_row

        for column in vertical_left:
            current_row = start_row
            for el in column:
                r = row_list[current_row]
                r.place(el)
                current_row += 1

        Row.fill_rows(row_list, start_row, current_row)

        final_rows.append(current_row)

        # Act 2. Place Horizontal Elements
        current_row = place_horizontal_elements(start_row)

        Row.fill_rows(row_list, start_row, current_row)

        final_rows.append(current_row)

        # Act 3. Place Right Vertical Elements
        max_row = max(*final_rows)
        row_count = max_row - start_row

        for column in vertical_right:
            current_row = start_row

            ## Attempt to spread them out across rows.
            ## TODO: Look into spreading out the left ones as well?
            rows_per_element = max(1, math.floor(row_count / len(column)))
            for el in column:
                r = row_list[current_row]
                r.place(el)
                current_row += rows_per_element

        final_rows.append(current_row)

        # Epilogue
        max_row = max(*final_rows)
        # Row.fill_rows(row_list, start_row, max_row)
        return max_row


class Slice_16(LRPlaceable):  # A Slice_16 is defined as 2 RAM8 slices (16 words)
    def __init__(self, instances: List[Instance]):
        raw_slices: Dict[int, List[Instance]] = {}
        raw_doregs: Dict[int, List[Instance]] = {}

        def process_slice(instance, slice):
            raw_slices[slice] = raw_slices.get(slice) or []
            raw_slices[slice].append(instance)

        def process_doreg(instance, port):
            raw_doregs[port] = raw_doregs.get(port) or []
            raw_doregs[port].append(instance)

        self.sieve(
            instances,
            [
                S(variable="slices", groups=["slice"], custom_behavior=process_slice),
                S(variable="doregs", groups=["port"], custom_behavior=process_doreg),
                S(variable="clk_diode"),
                S(variable="clkbuf"),
                S(variable="webufs", groups=["bit"]),
                S(variable="enbufs", groups=["port"]),
                S(variable="a_diodes", groups=["port", "address_bit"]),
                S(variable="abufs", groups=["port", "address_bit"]),
                S(variable="decoder_ands", groups=["port", "bit"]),
                S(variable="decoder_invs", groups=["port", "bit"]),
                S(variable="fbufenbufs", groups=["port", "bit"]),
                S(variable="ties", groups=["port", "bit"]),
                S(
                    variable="floatbufs",
                    groups=["port", "byte", "bit"],
                    group_rx_order=[2, 1, 3],
                ),
                S(
                    variable="floatbufsinvs",
                    groups=["port", "byte", "bit"],
                    group_rx_order=[2, 1, 3],
                ),
            ],
        )

        self.dicts_to_lists()

        self.slices = d2a({k: Slice(v) for k, v in raw_slices.items()})
        self.doregs = d2a({k: Outreg(v) for k, v in raw_doregs.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        def place_horizontal_elements(start_row: int):
            current_row = start_row
            r = row_list[current_row]

            for slice in self.slices:
                current_row = slice.place(row_list, current_row)

            port_count = len(self.ties)
            r = row_list[current_row]

            for port in range(port_count):
                r = row_list[current_row]
                for tie_group, tie in enumerate(self.ties[port]):
                    r.place(tie)
                    if len(self.floatbufsinvs) != 0:
                        for floatbufinv in self.floatbufsinvs[port][tie_group]:
                            r.place(floatbufinv)
                    for floatbuf in self.floatbufs[port][tie_group]:
                        r.place(floatbuf)

            current_row += 1

            for port in range(port_count):
                r = row_list[current_row]
                doreg = self.doregs[port]
                doreg.place(row_list, current_row)

            current_row += 1
            return current_row

        return self.lrplace(
            row_list=row_list,
            start_row=start_row,
            addresses=len(self.abufs),
            common=[self.clk_diode, self.clkbuf, *self.webufs],
            port_elements=[
                "enbufs",
                "a_diodes",
                "decoder_ands",
                "decoder_invs",
                "fbufenbufs",
                "abufs",
            ],
            place_horizontal_elements=place_horizontal_elements,
        )

    def word_count(self):
        return 16


class Block(LRPlaceable):  # A block is defined as 4 slices (32 words)
    def __init__(self, instances: List[Instance]):
        raw_blocks: Dict[int, List[Instance]] = {}
        raw_domuxes: Dict[int, List[Instance]] = {}

        def process_block(instance, block):
            raw_blocks[block] = raw_blocks.get(block) or []
            raw_blocks[block].append(instance)

        def process_raw_domuxes(instance, domux):
            raw_domuxes[domux] = raw_domuxes.get(domux) or []
            raw_domuxes[domux].append(instance)

        self.sieve(
            instances,
            [
                S(
                    variable="slice_16",
                    groups=["slice_16"],
                    custom_behavior=process_block,
                ),
                S(variable="webufs", groups=["bit"]),
                S(variable="enbufs", groups=["port"]),
                S(variable="abufs", groups=["port", "address_bit"]),
                S(variable="decoder_ands", groups=["port", "bit"]),
                S(variable="decoder_invs", groups=["port", "bit"]),
                S(variable="dibufs", groups=["bit"]),
                S(
                    variable="domuxes",
                    groups=["domux"],
                    custom_behavior=process_raw_domuxes,
                ),
                S(
                    variable="tiezero",
                ),
            ],
        )

        self.dicts_to_lists()

        self.blocks = d2a({k: Slice_16(v) for k, v in raw_blocks.items()})
        self.domuxes = d2a({k: Mux(v) for k, v in raw_domuxes.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        def place_horizontal_elements(start_row: int):
#            mux_row = 0
#            width1 = 0
#            width2 = 0
#            muxes = []
#            diodes = []
#            for domux in self.domuxes:
#               for mux in domux.muxes:
#                  for m in mux:
#                     muxes.append(m)
#               for diode in domux.mux_input_diodes:
#                  for d in diode:
#                     diodes.append(d)
#            
#            print( '===========================')
#            print(f'placing {len(muxes)} muxes')
#            print(f'{Row.supported_fill_sizes}')
#            print( '===========================')
#            fill_cell = Row.make_fill(mux_row, 1000, 0)
#            row_list[mux_row].place(fill_cell, ignore_tap=True)
#            mux_row += 1
#
#            i = 0
#            for mux in muxes:
#               row_list[mux_row].place(mux)
#               for d in diodes[i]:
#                  row_list[mux_row].place(d)
#                  width1 = mux.getMaster().getWidth() + d.getMaster().getWidth()
#               fill_cell = Row.make_fill(mux_row, 2000, 6)
#               row_list[mux_row].place(fill_cell, ignore_tap=True)
#               width1 += fill_cell.getMaster().getWidth()
#               i += 1
#               mux_row += 1
#
#            print(f'Width = {width1}')
#
#            while mux_row < 46:
#               fill_cell = Row.make_fill(mux_row, 1000, 0)
#               print(f"Fill width = {fill_cell.getMaster().getWidth()}")
#               row_list[mux_row].place(fill_cell, ignore_tap=True)
#               mux_row += 1
#
            current_row = start_row
            r = row_list[current_row]

            for dibuf in self.dibufs:
                r.place(dibuf)

            current_row += 1
            for block in self.blocks:
                current_row = block.place(row_list, current_row)

            if self.tiezero is not None:
                r = row_list[current_row]
                r.place(self.tiezero)
                current_row += 1

#            print(f'current_row: {current_row}')
#            print(f'row_list:    {len(row_list)}')
#            Row.fill_rows(row_list, current_row, current_row+1)
#            Row.fill_rows(row_list, current_row+1, current_row+2)
            for domux in self.domuxes:
                current_row = domux.place(row_list, current_row)

#            for i in range(current_row+2):
#               print(f'Row {i} X={row_list[i].x}')

            return current_row+2

        return self.lrplace(
            row_list=row_list,
            start_row=start_row,
            addresses=len(self.abufs),
            common=[*self.webufs],
            port_elements=[
                "enbufs",
                "abufs",
                "decoder_ands",
                "decoder_invs",
            ],
            place_horizontal_elements=place_horizontal_elements,
        )

    def word_count(self):
        return 32


class HigherLevelPlaceable(LRPlaceable):
    def __init__(self, instances: List[Instance], block_size: int):
        raw_blocks: Dict[int, List[Instance]] = {}

        def process_block(instance, block):
            raw_blocks[block] = raw_blocks.get(block) or []
            raw_blocks[block].append(instance)

        raw_domuxes: Dict[int, List[Instance]] = {}

        def process_raw_domuxes(instance, domux):
            raw_domuxes[domux] = raw_domuxes.get(domux) or []
            raw_domuxes[domux].append(instance)

        self.clkbuf = None

        self.sieve(
            instances,
            [
                S(
                    variable=f"block{block_size}",
                    groups=["block"],
                    custom_behavior=process_block,
                ),
                S(
                    variable="domuxes",
                    groups=["domux"],
                    custom_behavior=process_raw_domuxes,
                ),
                S(variable="clk_diode"),
                S(variable="clkbuf"),
                S(variable="tiezero"),
                S(variable="di_diodes", groups=["bit"]),
                S(variable="dibufs", groups=["bit"]),
                S(variable="webufs", groups=["bit"]),
                S(variable="enbufs", groups=["port"]),
                S(variable="decoder_ands", groups=["port", "bit"]),
                S(variable="decoder_invs", groups=["port", "bit"]),
                S(variable="abufs", groups=["port", "address_bit"]),
                S(variable="a_diodes", groups=["port", "address_bit"]),
            ],
        )

        self.dicts_to_lists()

        self.blocks = d2a(
            {k: create_hierarchy(v, block_size) for k, v in raw_blocks.items()}
        )
        self.domuxes = d2a({k: Mux(v) for k, v in raw_domuxes.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        def symmetrically_placeable():
            return self.word_count() > 128

        current_row = start_row

        def place_horizontal_elements(start_row: int):
            # all of the big designs include 4 instances
            # of the smaller block they are constituted of
            # so they can all be 1:1 if they are 2x2
            # the smallest 1:1 is the 128 word block
            # it is placed all on top of each other
            current_row = start_row
            r = row_list[current_row]

            for diode, dibuf in zip_longest(self.di_diodes, self.dibufs):
                if diode is not None:
                    r.place(diode)
                r.place(dibuf)

            if self.tiezero is not None:
                r.place(self.tiezero)

            current_row += 1

            partition_cap = int(math.sqrt(len(self.blocks)))
            if symmetrically_placeable():
                max_rows = []
                for i in range(len(self.blocks)):
                    if i == partition_cap:
                        current_row = start_row
                    current_row = self.blocks[i].place(row_list, current_row)
                    max_rows.append(current_row)
                current_row = max(max_rows)
            else:
                for block in self.blocks:
                    current_row = block.place(row_list, current_row)

            for domux in self.domuxes:
                current_row = domux.place(row_list, current_row)

            return current_row

        return self.lrplace(
            row_list=row_list,
            start_row=current_row,
            addresses=len(self.domuxes),
            common=[
                *([self.clkbuf, self.clk_diode] if self.clkbuf is not None else []),
                *self.webufs,
            ],
            port_elements=[
                "enbufs",
                "abufs",
                "a_diodes",
                "decoder_ands",
                "decoder_invs",
            ],
            place_horizontal_elements=place_horizontal_elements,
        )

    def word_count(self):
        return len(self.blocks) * (self.blocks[0].word_count())


def create_hierarchy(instances, word_count, left, placer=None, channels=None):
    hierarchy = None
    if placer == "IhpCfgMem_16":
        from .ihp_cfgmem_data import IhpCfgMem_16

        hierarchy = IhpCfgMem_16(instances, left, channels)
    elif placer is not None:
        raise DataError("Unknown placer '%s' requested by model config." % placer)
    elif word_count == 1:
        hierarchy = Word(instances)
    elif word_count == 8:
        hierarchy = Slice(instances)
    elif word_count == 16:
        hierarchy = CfgMem_16(instances, left)
    elif word_count == 32:
        hierarchy = Block(instances)
    else:
        """
        I derived this equation based on the structure we have.
        Feel free to independently verify it.

        Valid for 128 <= 𝒙 <= 2048:

            𝒇(𝒙) = 32 * 4 ^ ⌈log2(𝒙 / 128) / 2⌉
        """

        def f(x):
            return 32 * (4 ** math.ceil(math.log2(x / 128) / 2))

        block_size = f(word_count)
        hierarchy = HigherLevelPlaceable(instances, block_size)
    return hierarchy
