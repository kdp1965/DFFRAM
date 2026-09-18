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
Move the bottom-edge pin shapes of selected pins to another (vertical) layer.

Runs after the PDN so the target layer's power stripes exist: a pin whose
shape would land on or next to a stripe (or another pin already on that
layer) is shifted to the nearest free routing track.  Pin length and width
are kept; the placement status is kept.  Meant for putting a macro's data
pins on the parent's under-used top vertical layer (Metal4 on CMOS5L, which
also carries the power stripes).
"""

import re

import click
import odb

from reader import click_odb


@click.command()
@click.option("--pins", required=True, help="Regex of the pins to move")
@click.option("--layer", default="Metal4", help="Target layer")
@click.option("--from-layer", default="Metal2", help="Layer the pins are on now")
@click.option(
    "--clearance",
    default=0.3,
    type=float,
    help="Spacing (um) kept from stripes and other pins on the target layer",
)
@click_odb
def main(reader, pins, layer, from_layer, clearance):
    block = reader.block
    tech = reader.tech
    u = block.getDbUnitsPerMicron()
    target = tech.findLayer(layer)
    if target is None:
        raise click.ClickException(f"layer {layer} not in the tech")
    clr = int(round(clearance * u))
    die = block.getDieArea()

    # x intervals already taken on the target layer, grown by the clearance
    blocked = []
    for net in block.getNets():
        for swire in net.getSWires():
            for box in swire.getWires():
                lyr = box.getTechLayer()
                if lyr is not None and lyr.getName() == layer:
                    blocked.append((box.xMin() - clr, box.xMax() + clr))
    for bterm in block.getBTerms():
        for bpin in bterm.getBPins():
            for box in bpin.getBoxes():
                if box.getTechLayer().getName() == layer:
                    blocked.append((box.xMin() - clr, box.xMax() + clr))
    stripes = len(blocked)

    grid = block.findTrackGrid(target)
    tracks = sorted(grid.getGridX()) if grid is not None else []

    def free(xc, w):
        lo, hi = xc - w // 2, xc + w // 2
        return all(not (lo < bhi and hi > blo) for blo, bhi in blocked)

    pattern = re.compile(pins)
    moved = shifted = 0
    for bterm in block.getBTerms():
        if not pattern.search(bterm.getName()):
            continue
        for bpin in list(bterm.getBPins()):
            boxes = [
                b
                for b in bpin.getBoxes()
                if b.getTechLayer().getName() == from_layer and b.yMin() == die.yMin()
            ]
            if not boxes:
                continue
            b = boxes[0]
            w = b.xMax() - b.xMin()
            xc = (b.xMin() + b.xMax()) // 2
            y0, y1 = b.yMin(), b.yMax()
            if not free(xc, w):
                new_xc = next(
                    (x for x in sorted(tracks, key=lambda x: abs(x - xc)) if free(x, w)),
                    None,
                )
                if new_xc is None:
                    raise click.ClickException(f"no free {layer} track for {bterm.getName()}")
                print(
                    f"{bterm.getName()}: {xc / u:.2f} um sits on a {layer} stripe, "
                    f"moved to {new_xc / u:.2f} um"
                )
                xc = new_xc
                shifted += 1
            status = bpin.getPlacementStatus()
            odb.dbBPin.destroy(bpin)
            new_pin = odb.dbBPin.create(bterm)
            odb.dbBox.create(new_pin, target, xc - w // 2, y0, xc + w // 2, y1)
            new_pin.setPlacementStatus(status if status != "NONE" else "PLACED")
            blocked.append((xc - w // 2 - clr, xc + w // 2 + clr))
            moved += 1

    print(
        f"moved {moved} bottom-edge pin shapes from {from_layer} to {layer} "
        f"({shifted} shifted off the {stripes} blocked intervals)"
    )


if __name__ == "__main__":
    main()
