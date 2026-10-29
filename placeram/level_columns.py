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
Level the right-hand column of a placed RAM.

The word rows end with the words' own cells and are padded to the widest
of them; then the placer appends a column of support cells to every row -
the decoder's gates and buffers (Decoder3x8.place puts its three address
buffers and the enable buffer in one row, an AND and an inverter in each of
the next), the write-enable and clock buffers, the block-level address
buffers, enable buffer and diodes (LRPlaceable.lrplace spreads them down
the rows) - each pass appending to whatever the row already holds.  The
result is a ragged right edge: on the 32x32 ram_ao the column spans up to
62 um in the fullest row while the cells of all rows would fit in 36 um if
they were spread evenly, and the fullest row is what sets the macro's
width (cli.Placer.place: the widest row plus the row margin).

This pass runs after the whole hierarchy is placed and before the rows are
filled.  It takes every cell right of a row's fixed part (the words, the
combine gates, the output registers, the fills already placed) as movable,
and moves cells between neighbouring rows - at most `max_shift` rows up or
down, so a decoder gate stays beside the word it selects and a buffer near
its load - until no row's column is wider than the evenly spread width
plus one cell.  The column cells of the touched rows are then re-placed
from the row's fixed end, in their new order, and the Row objects' x is
updated so the width computation and the fill pass see the new ends.

Ken's CFGMEM macros did this by hand in their placer (cells slid up a row
or two into the gaps); here it is a generic post-pass so the ram_ao
placement code stays as it is.
"""
import re
from typing import Dict, List, Tuple

from .row import Row

import odb
from odb import dbInst as Instance

# Cells that belong to the array and the fixed structure: never moved.
FIXED_RX = re.compile(r"(WORD\[\d+\]|\.BIT\[\d+\]\.|Do0_REG|OUTREG|^fill_|^tap_|\.fill_|\.tap_)")


def _name(inst: Instance) -> str:
    # odb hands back the names with the DEF's backslash escapes (WORD\[1\]):
    # strip them before matching, or nothing matches and every cell moves
    # (the first build with this pass scrambled the whole array, 2026-10-29)
    return inst.getName().replace("\\", "")


def _is_fill(inst: Instance) -> bool:
    name = _name(inst)
    master = inst.getMaster().getName()
    return bool(re.search(r"(^|\.)(fill|tap)_\d+_\d+$", name)) or "fill" in master or "decap" in master


def level_right_columns(block, rows: List[Row], last_row: int, max_shift: int = 2) -> Tuple[float, float]:
    """Returns (widest row before, widest row after) in database units."""
    if max_shift <= 0:
        return (0.0, 0.0)

    # Row objects by their y, instances by row.
    row_by_y: Dict[int, Row] = {}
    for r in rows[:last_row]:
        row_by_y[int(r.y)] = r
    per_row: Dict[int, List[Instance]] = {y: [] for y in row_by_y}
    for inst in block.getInsts():
        if not inst.isPlaced():
            continue
        x, y = inst.getLocation()
        if y in per_row:
            per_row[y].append(inst)

    def width_of(inst: Instance) -> int:
        return inst.getMaster().getWidth()

    # Per row: the fixed end (the last cell of the array, the combine gates
    # or the output register) and the movable cells right of it.  The
    # placer's own fills right of that end go: every level of the hierarchy
    # padded the rows to the widest one before appending its column, so the
    # fills sit between the columns' cells (and a fixed end that counted them
    # left nothing movable, 2026-10-29); the fill pass after this one pads the
    # rows to the new width.
    fixed_end: Dict[int, int] = {}
    movable: Dict[int, List[Instance]] = {}
    ordered_ys = sorted(row_by_y)
    doomed: List[Instance] = []
    n_fixed = 0
    for y in ordered_ys:
        insts = sorted(per_row[y], key=lambda i: i.getLocation()[0])
        end = row_by_y[y].xmin
        others = []
        for inst in insts:
            x = inst.getLocation()[0]
            if FIXED_RX.search(_name(inst)) and not _is_fill(inst):
                end = max(end, x + width_of(inst))
                n_fixed += 1
            else:
                others.append(inst)
        mov, fills = [], []
        for inst in others:
            x = inst.getLocation()[0]
            if x + width_of(inst) <= end:
                continue  # a fill or buffer inside the array: stays
            (fills if _is_fill(inst) else mov).append(inst)
        fixed_end[y] = end
        movable[y] = mov
        doomed += fills
    n_mov = sum(len(movable[y]) for y in ordered_ys)
    if n_mov > n_fixed:
        raise RuntimeError(
            "level_right_columns: %d movable against %d fixed cells - the fixed-cell patterns do not match this design's names; nothing moved"
            % (n_mov, n_fixed)
        )
    # the fills go only now: a destroyed instance must not be touched again
    # (per_row still lists them; getName() on one crashed OpenROAD)
    for inst in doomed:
        odb.dbInst.destroy(inst)
    per_row = None

    def col_width(y: int) -> int:
        return sum(width_of(i) for i in movable[y])

    rows_with_columns = [y for y in ordered_ys if movable[y]]
    if not rows_with_columns:
        return (0.0, 0.0)
    before = max(fixed_end[y] + col_width(y) for y in ordered_ys)

    total = sum(col_width(y) for y in rows_with_columns)
    # the column starts where the row's fixed part ends, which differs a
    # little between rows (the word rows are padded to the widest word row,
    # the combine rows end earlier): level the row ENDS, not the column
    # widths, so the target is an end x
    biggest_cell = max(width_of(i) for y in rows_with_columns for i in movable[y])
    n = len(rows_with_columns)
    target_end = (sum(fixed_end[y] for y in rows_with_columns) + total) / n + biggest_cell

    def end_of(y: int) -> int:
        return fixed_end[y] + col_width(y)

    index = {y: k for k, y in enumerate(ordered_ys)}
    moved = 0
    changed = True
    while changed:
        changed = False
        for y in sorted(ordered_ys, key=end_of, reverse=True):
            if end_of(y) <= target_end or not movable[y]:
                continue
            # the widest cell first: it frees the most
            for inst in sorted(movable[y], key=width_of, reverse=True):
                w = width_of(inst)
                best = None
                for d in range(1, max_shift + 1):
                    for k in (index[y] - d, index[y] + d):
                        if 0 <= k < len(ordered_ys):
                            yy = ordered_ys[k]
                            if end_of(yy) + w <= target_end and (best is None or end_of(yy) < end_of(best)):
                                best = yy
                if best is not None:
                    movable[y].remove(inst)
                    movable[best].append(inst)
                    moved += 1
                    changed = True
                    break
            # one move per row per sweep keeps the leveling even

    # Re-place the columns of every row from its fixed end.
    for y in ordered_ys:
        r = row_by_y[y]
        x = fixed_end[y]
        for inst in sorted(movable[y], key=width_of, reverse=True):
            inst.setOrient(r.orientation)
            inst.setLocation(int(x), int(r.y))
            inst.setPlacementStatus("PLACED")
            x += width_of(inst)
        r.x = int(x)
    after = max(end_of(y) for y in ordered_ys)
    dbu = block.getDbUnitsPerMicron()
    print(
        "Leveled the right columns: %d cells moved (shift <= %d rows), %d fills dropped; widest row %.2f -> %.2f um"
        % (moved, max_shift, len(doomed), before / dbu, after / dbu)
    )
    return (before, after)
