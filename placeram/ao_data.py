# -*- coding: utf8 -*-
# The AND-OR read path's placement (models/ram_ao, 2026-10-16): the same
# rows as placeram/data.py's RAM32 - a word per row, the slice's decoder in
# a side column - with a nand2 beside every storage cell instead of an
# ebufn, one extra row per 8-word slice for the nand4s that combine its
# words (and, in the 16-word block's second slice, the or4s that combine its
# two slices), and no float buffers or tie row.  Instance names:
#   WORD[w].W.BYTE[b].B.BIT[i].STORAGE / .OGATE  (BYTE_AO)
#   WORD[w].W.BYTE[b].B.SEL0BUF / CG / CGAND / CLKINV / DIODE_CLK
#   BIT[i].HALF[h].N4   (RAM8_AO: words 4h..4h+3 of bit i)
#   BIT[i].OR4          (RAM16_AO)
from .row import Row
from .util import d2a
from .placeable import Placeable, DataError
from .common_data import Decoder3x8
from .data import Block, LRPlaceable, Outreg

from odb import dbInst as Instance

from typing import List, Dict

S = Placeable.Sieve


class BitAO(Placeable):
    def __init__(self, instances: List[Instance]):
        self.sieve(instances, [S(variable="store"), S(variable="ogate")])
        self.dicts_to_lists()

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]
        r.place(self.store)
        r.place(self.ogate)
        return start_row


class ByteAO(Placeable):
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
                S(variable="selbuf"),
            ],
        )
        self.dicts_to_lists()
        self.bits = d2a({k: BitAO(v) for k, v in raw_bits.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        r = row_list[start_row]
        for bit in self.bits:
            bit.place(row_list, start_row)
        r.place(self.clockgate)
        r.place(self.cgand)
        if self.clkdiode is not None:
            r.place(self.clkdiode)
        r.place(self.selbuf)
        if self.clkinv is not None:
            r.place(self.clkinv)
        return start_row


class WordAO(Placeable):
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
        self.bytes = d2a({k: ByteAO(v) for k, v in raw_bytes.items()})

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


class SliceAO(Placeable):  # 8 words, then a row of nand4s (two per bit)
    def __init__(self, instances: List[Instance]):
        raw_words: Dict[int, List[Instance]] = {}

        def process_word(instance, word):
            raw_words[word] = raw_words.get(word) or []
            raw_words[word].append(instance)

        raw_decoders: Dict[int, List[Instance]] = {}

        def process_decoder(instance, decoder):
            raw_decoders[decoder] = raw_decoders.get(decoder) or []
            raw_decoders[decoder].append(instance)

        raw_nands: Dict[int, Dict[int, Instance]] = {}

        def process_nand(instance, bit, half):
            # the sieve's own lists sort the regex groups as strings (0, 1, 10,
            # 11, ...): keep the bit order numeric or the nand4s land under
            # the wrong columns
            raw_nands.setdefault(int(bit), {})[int(half)] = instance

        self.sieve(
            instances,
            [
                S(variable="words", groups=["word"], custom_behavior=process_word),
                S(variable="decoders", groups=["port"], custom_behavior=process_decoder),
                S(variable="nands", groups=["bit", "half"], custom_behavior=process_nand),
                S(variable="clkbuf"),
                S(variable="webufs", groups=["line"]),
                S(variable="tiezero"),
            ],
        )
        self.dicts_to_lists()
        self.nands = [[raw_nands[b][h] for h in sorted(raw_nands[b])] for b in sorted(raw_nands)]
        self.decoders = d2a({k: Decoder3x8(v) for k, v in raw_decoders.items()})
        self.words = d2a({k: WordAO(v) for k, v in raw_words.items()})
        if len(self.words) != 8:
            raise DataError("SliceAO has (%i/8) words." % len(self.words))

    @staticmethod
    def pad_to(r: Row, x: int):
        """Fill cells from the row's current end up to x (database units)."""
        sites = int(round((x - r.x) / Row.sw))
        for size in Row.supported_fill_sizes:  # largest first
            while sites >= size:
                r.place(Row.create_fill("fill_%i_%i" % (r.ordinal, r.fill_counter), size), ignore_tap=True)
                r.fill_counter += 1
                sites -= size

    def place(self, row_list: List[Row], start_row: int = 0, extra_per_bit=None):
        """As data.Slice.place: odd address ports' decoders left, even ones
        right; the words one per row; then the nand4 row, each byte's eight
        pairs (and `extra_per_bit`, the 16-word block's or4s, in the last
        slice) padded out to start under that byte's column in the word rows:
        two nand4 and an or4 are 16 sites to a bit's 15 of storage and
        nand2, and a byte's clock gate, buffers and diode make up the
        difference, so a bit's eight terms and its or4 stay within a few
        sites of its column instead of drifting up to 70 um (met1 at 368%
        of capacity when they were packed from the left, 2026-10-16).
        Returns the row after the nand4 row."""
        vertical_left, vertical_right = [], []
        right = True
        for decoder in self.decoders:
            (vertical_right if right else vertical_left).append(decoder)
            right = not right

        final_rows = []
        current_row = start_row
        for decoder in vertical_left:
            current_row = decoder.place(row_list, start_row)
        final_rows.append(current_row)

        current_row = start_row
        for word in self.words:
            current_row = word.place(row_list, current_row)
        Row.fill_rows(row_list, start_row, current_row)

        # the combine row, byte by byte under the word rows' byte columns
        self.nand_row = current_row
        r = row_list[current_row]
        word0 = self.words[0]
        bit = 0
        for byte in word0.bytes:
            self.pad_to(r, byte.bits[0].store.getLocation()[0])
            for _ in byte.bits:
                for n4 in self.nands[bit]:
                    r.place(n4)
                if extra_per_bit is not None:
                    r.place(extra_per_bit[bit])
                bit += 1
        current_row += 1

        last_column = [*self.webufs]
        place_clkbuf_alone = len(last_column) == 8
        if not place_clkbuf_alone:
            last_column.append(self.clkbuf)
        while len(last_column) < 8:
            last_column.append(None)
        for i in range(8):
            if last_column[i] is not None:
                row_list[start_row + i].place(last_column[i])
        if self.tiezero is not None:
            row_list[start_row].place(self.tiezero)
        if place_clkbuf_alone:
            row_list[start_row].place(self.clkbuf)
        final_rows.append(current_row)

        current_row = start_row
        for decoder in vertical_right:
            current_row = decoder.place(row_list, start_row)
        final_rows.append(current_row)

        return max(*final_rows)

    def word_count(self):
        return 8


class Slice16AO(LRPlaceable):  # 2 slices, the or4s in the second slice's nand4 row, then the output register
    GAP_ROWS = 0  # as data.Slice_16.GAP_ROWS

    def __init__(self, instances: List[Instance]):
        raw_slices: Dict[int, List[Instance]] = {}
        raw_doregs: Dict[int, List[Instance]] = {}

        def process_slice(instance, slice):
            raw_slices[slice] = raw_slices.get(slice) or []
            raw_slices[slice].append(instance)

        def process_doreg(instance, port):
            raw_doregs[port] = raw_doregs.get(port) or []
            raw_doregs[port].append(instance)

        raw_ors: Dict[int, Instance] = {}

        def process_or(instance, bit):
            raw_ors[int(bit)] = instance  # numeric bit order (see SliceAO)

        self.sieve(
            instances,
            [
                S(variable="slices", groups=["slice"], custom_behavior=process_slice),
                S(variable="doregs", groups=["port"], custom_behavior=process_doreg),
                S(variable="ors", groups=["bit"], custom_behavior=process_or),
                S(variable="clk_diode"),
                S(variable="clkbuf"),
                S(variable="webufs", groups=["bit"]),
                S(variable="enbufs", groups=["port"]),
                S(variable="a_diodes", groups=["port", "address_bit"]),
                S(variable="abufs", groups=["port", "address_bit"]),
                S(variable="decoder_ands", groups=["port", "bit"]),
                S(variable="decoder_invs", groups=["port", "bit"]),
            ],
        )
        self.dicts_to_lists()
        self.ors = [raw_ors[b] for b in sorted(raw_ors)]
        self.slices = d2a({k: SliceAO(v) for k, v in raw_slices.items()})
        self.doregs = d2a({k: Outreg(v) for k, v in raw_doregs.items()})

    def place(self, row_list: List[Row], start_row: int = 0):
        def place_horizontal_elements(start_row: int):
            current_row = start_row
            last = len(self.slices) - 1
            for i, slice in enumerate(self.slices):
                # the or4s go into the last slice's nand4 row, beside each bit's nand4 pair
                current_row = slice.place(row_list, current_row, extra_per_bit=self.ors if i == last else None)
            for doreg in self.doregs:
                doreg.place(row_list, current_row)
            current_row += 1 + self.GAP_ROWS
            return current_row

        return self.lrplace(
            row_list=row_list,
            start_row=start_row,
            addresses=len(self.abufs),
            common=[self.clk_diode, self.clkbuf, *self.webufs],
            port_elements=["enbufs", "a_diodes", "decoder_ands", "decoder_invs", "abufs"],
            place_horizontal_elements=place_horizontal_elements,
        )

    def word_count(self):
        return 16


class BlockAO(Block):
    Slice16Class = Slice16AO
