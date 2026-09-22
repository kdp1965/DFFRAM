"""
Move bottom-edge pin shapes out of the macro's route-through channels.

The channels are the locked decap columns the placer put through the array
(instances named chan_<row>_<k>); their x spans, read from row 0, are the
tracks the parent design's router is meant to have for itself, top to
bottom of the macro.  The IO placer spreads the bottom-edge pins evenly and
knows nothing about them, so any pin whose shape lands in a channel (plus a
clearance) is slid sideways to the nearest position outside it, snapped to
the pin layer's track grid and kept clear of its neighbours.  A no-op when
the design has no channels.
"""
import re

import click
import odb

from reader import click_odb


def channel_spans(block, clearance):
    spans = []
    for inst in block.getInsts():
        if re.match(r"chan_0_\d+$", inst.getName()):
            bbox = inst.getBBox()
            spans.append((bbox.xMin() - clearance, bbox.xMax() + clearance))
    return sorted(spans)


@click.command()
@click.option(
    "--clearance",
    default=0.3,
    type=float,
    help="Spacing (um) kept between a pin shape and a channel or another pin",
)
@click_odb
def main(reader, clearance):
    block = reader.block
    u = block.getDbUnitsPerMicron()
    clr = int(round(clearance * u))
    die = block.getDieArea()
    spans = channel_spans(block, clr)
    if not spans:
        print("no route-through channels in the design; pins left as placed")
        return
    print(
        "channels (um, with clearance): "
        + ", ".join(f"{a / u:.2f}..{b / u:.2f}" for a, b in spans)
    )
    edge = []
    for bterm in block.getBTerms():
        for bpin in bterm.getBPins():
            for box in bpin.getBoxes():
                if box.yMin() == die.yMin():
                    edge.append([bterm, bpin, box])
    occupied = [(b.xMin() - clr, b.xMax() + clr) for _, _, b in edge]

    def in_span(lo, hi, spans_):
        return any(lo < s_hi and hi > s_lo for s_lo, s_hi in spans_)

    moved = 0
    for i, (bterm, bpin, box) in enumerate(edge):
        lo, hi = box.xMin(), box.xMax()
        if not in_span(lo, hi, spans):
            continue
        w = hi - lo
        layer = box.getTechLayer()
        grid = block.findTrackGrid(layer)
        tracks = sorted(grid.getGridX()) if grid is not None else []
        others = occupied[:i] + occupied[i + 1 :]
        xc = (lo + hi) // 2
        new_xc = next(
            (
                x
                for x in sorted(tracks, key=lambda x: abs(x - xc))
                if not in_span(x - w // 2, x + w // 2, spans)
                and not in_span(x - w // 2, x + w // 2, others)
                and die.xMin() < x - w // 2
                and x + w // 2 < die.xMax()
            ),
            None,
        )
        if new_xc is None:
            raise click.ClickException(f"no free position beside a channel for {bterm.getName()}")
        y0, y1 = box.yMin(), box.yMax()
        status = bpin.getPlacementStatus()
        odb.dbBPin.destroy(bpin)
        new_pin = odb.dbBPin.create(bterm)
        odb.dbBox.create(new_pin, layer, new_xc - w // 2, y0, new_xc + w // 2, y1)
        new_pin.setPlacementStatus(status if status != "NONE" else "PLACED")
        occupied[i] = (new_xc - w // 2 - clr, new_xc + w // 2 + clr)
        print(f"{bterm.getName()}: {xc / u:.2f} um is in a channel, moved to {new_xc / u:.2f} um")
        moved += 1
    print(f"moved {moved} bottom-edge pin shape(s) out of {len(spans)} channel(s)")


if __name__ == "__main__":
    main()
