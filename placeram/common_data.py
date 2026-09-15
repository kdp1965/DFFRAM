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
from .row import Row
from .util import d2a
from .placeable import Placeable

from odb import dbInst as Instance

from typing import List
from itertools import zip_longest

P = Placeable
S = Placeable.Sieve


class Mux(Placeable):
    """
    Constraint: The number of selection buffers is necessarily == the number of bytes.
    """

    def __init__(self, instances: List[Instance]):
        self.sieve(
            instances,
            [
                S(variable="sel_diodes", groups=["selection_line"]),
                S(variable="selbufs", groups=["selection_line", "byte"]),
                S(variable="muxes", groups=["byte", "bit"]),
                S(
                    variable="mux_input_diodes",
                    groups=["byte", "bit", "line"],
                    group_rx_order=[1, 3, 2],
                ),
            ],
        )
        self.dicts_to_lists()

    def place(self, row_list: List[Row], start_row: int = 0):
        current_row = start_row

        row = row_list[current_row]
        diode_row = None

        fill_from = current_row
        row_increment = 1

        if len(self.sel_diodes) or len(self.mux_input_diodes):
            row = row_list[current_row + 1]
            diode_row = row_list[current_row]
            row_increment = 2

        fill_to = current_row + row_increment

        for diode, line_buffers in zip_longest(self.sel_diodes, self.selbufs):
            if diode is not None:
                diode_row.place(diode)
            for buf in line_buffers:
                row.place(buf)
            Row.fill_rows(row_list, fill_from, fill_to)

        byte = len(self.muxes)
        for i in range(byte):
            for mux, line_diodes in zip_longest(
                self.muxes[i], self.mux_input_diodes[i]
            ):
                row.place(mux)
                if line_diodes is not None:
                    for diode in line_diodes:
                        diode_row.place(diode)
                Row.fill_rows(row_list, fill_from, fill_to)

        return current_row + row_increment


class Decoder3x8(Placeable):
    def __init__(self, instances: List[Instance]):
        and_gates = {}
        def process_and(instance, bit):
            bit = int(bit) 
            and_gates[bit] = instance

        self.sieve(
            instances,
            [
                S(variable="enbuf"),
                S(variable="and_gates", groups=["gate"], custom_behavior=process_and),
                S(variable="abufs", groups=["address_bit"]),
                S(variable="invs", groups=["gate"]),
            ],
        )
        self.dicts_to_lists()
        self.and_gates = and_gates

    def place(self, row_list: List[Row], start_row: int = 0):
        """
        By placing this decoder, you agree that rows[start_row:start_row+7]
        are at the sole mercy of this function.
        """

        ands_placeable = self.and_gates
        buffers_placeable = [*self.abufs, self.enbuf, None, None, None, None]
        invs_placeable = self.invs

        current_row = start_row
        r = row_list[current_row]
        for i in range(3):
            buf = buffers_placeable[i]
            r.place(buf)
        r.place(self.enbuf)
        current_row += 1

        for i in range(8):
            print(f'Placing 3x8 mux, current_row = {current_row}')
            r = row_list[current_row]
            r.place(ands_placeable[i])
            if i < len(self.invs):
                r.place(invs_placeable[i])
            current_row += 1
            if i == 3:
                current_row += 1

        return start_row + 8

class Decoder1x2(Placeable):
    def __init__(self, instances):
        self.sieve(
            instances,
            [
                S(
                    variable="and_gates",
                    groups=["address_bit"],
                ),
                S(
                    variable="invs",
                    groups=["address_bit"],
                ),
            ],
        )
        self.dicts_to_lists()

    def place(self, row_list, start_row=0):
        r = row_list[start_row]
        for i in range(
            2
        ):  # range is 2 because 1x2 has 2 AND gates put on on top of each other
            r.place(self.and_gates[i])
            if i < len(self.invs):
                r.place(self.invs[i])

        return start_row + 1


class Decoder2x4(Placeable):
    def __init__(self, instances):
        self.sieve(
            instances,
            [
                S(
                    variable="and_gates",
                    groups=["address_bit"],
                ),
                S(
                    variable="invs",
                    groups=["address_bit"],
                ),
            ],
        )
        self.dicts_to_lists()

    def place(self, row_list, start_row=0):
        for i in range(
            4
        ):  # range is 4 because 2x4 has 4 AND gates put on on top of each other
            r = row_list[start_row + i]
            r.place(self.and_gates[i])
            if i < len(self.invs):
                r.place(self.invs[i])

        return start_row + 4


class Decoder4x16(Placeable):
    def __init__(self, instances):
        raw_d1x2 = []

        def process_d1x2_element(instance):
            raw_d1x2.append(instance)

        raw_d3x8 = {}

        def process_d3x8_element(instance, decoder):
            raw_d3x8[decoder] = raw_d3x8.get(decoder) or []
            raw_d3x8[decoder].append(instance)

        self.enbuf = None
        self.sieve(
            instances,
            [
                S(variable="decoder1x2", custom_behavior=process_d1x2_element),
                S(
                    variable="decoders3x8",
                    groups=["decoder"],
                    custom_behavior=process_d3x8_element,
                ),
            ],
        )

        self.dicts_to_lists()

        self.decoders3x8 = d2a({k: Decoder3x8(v) for k, v in raw_d3x8.items()})
        self.decoder1x2 = Decoder1x2(raw_d1x2)

    def place(self, row_list, start_row=0, decoder1x2_start_row=0, flip=False):
        r = row_list[start_row]

        if flip:
            self.decoder1x2.place(row_list, decoder1x2_start_row)
            for idx in range(len(self.decoders3x8)):
                self.decoders3x8[idx].place(row_list, idx * 8+5)
            # Row.fill_rows(row_list, start_row, current_row)

        else:
            for idx in range(len(self.decoders3x8)):
                self.decoders3x8[idx].place(row_list, idx * 10)

            self.decoder1x2.place(row_list, decoder1x2_start_row + 5)
        return start_row + 16  # 4x16 has 2 3x8 on top of each other and each is 8 rows

class Decoder5x32(Placeable):
    def __init__(self, instances):
        raw_d2x4 = []

        def process_d2x4_element(instance):
            raw_d2x4.append(instance)

        raw_d3x8 = {}

        def process_d3x8_element(instance, decoder):
            raw_d3x8[decoder] = raw_d3x8.get(decoder) or []
            raw_d3x8[decoder].append(instance)

        self.enbuf = None
        self.sieve(
            instances,
            [
                S(variable="tie"),
                S(variable="decoder2x4", custom_behavior=process_d2x4_element),
                S(
                    variable="decoders3x8",
                    groups=["decoder"],
                    custom_behavior=process_d3x8_element,
                ),
            ],
        )

        self.dicts_to_lists()

        self.decoders3x8 = d2a({k: Decoder3x8(v) for k, v in raw_d3x8.items()})
        self.decoder2x4 = Decoder2x4(raw_d2x4)

    def place(self, row_list, start_row=0, decoder2x4_start_row=0, flip=False):
        r = row_list[start_row]
        r.place(self.tie)

        if flip:
            self.decoder2x4.place(row_list, decoder2x4_start_row)
            for idx in range(len(self.decoders3x8)):
                self.decoders3x8[idx].place(row_list, idx * 8)
            # Row.fill_rows(row_list, start_row, current_row)

        else:
            for idx in range(len(self.decoders3x8)):
                self.decoders3x8[idx].place(row_list, idx * 8)

            self.decoder2x4.place(row_list, decoder2x4_start_row)
            # Row.fill_rows(row_list, start_row, current_row)
        return start_row + 32  # 5x32 has 4 3x8 on top of each other and each is 8 rows
