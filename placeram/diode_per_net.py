"""
One antenna diode on every long, low-fanout net, placed in the macro's spare
rows (TOP_SPARE_ROWS), before routing.

Tiny Tapeout's precheck runs the foundry's KLayout antenna deck on the
flattened GDS.  GF180's ANT.4 / ANT.16 credit a net only for explicit diodes
(n_diode / p_diode / nwell; a diode is worth 15 gates under the thick-gate
rule), while OpenROAD's model credits a driver's drain diffusion too, so the
flow's antenna check and repair never saw the 20 Metal3 nets the deck
flagged in the 32x32 ram_ao (Do mux inputs, Di lines, address and WE
buffers: 330-665 um of wire on one or two gates).  High-fanout nets (the
clocks, the decoder lines) have the gate area to be safe; the risk is a
long net with few pins, so that is what gets a diode here.  The RAM's rows
are packed with logic and placeram's fill / tie cells, hence the spare
rows, which hold fill only: the diode replaces the fill at the net's x
(OpenROAD.FillInsertion refills around it later) and the router brings the
net to it.  Same command line as placeram so the DFFRAM flow can run it as
an odbpy step.
"""
import click
import odb

from .util import eprint


@click.command()
@click.option("-o", "--output-odb", required=True)
@click.option("--output-def", type=str, required=False, default=None)
@click.option("-l", "--input-lef", default=[], multiple=True, type=str, help="ignored")
@click.option("--diode-cell", required=True, help="the antenna diode cell")
@click.option("--diode-pin", required=True, help="its pin")
@click.option("--threshold", type=float, default=250.0, help="a net's half-perimeter in um from which it gets a diode")
@click.option("--max-pins", type=int, default=16, help="nets with more pins have the gate area to be safe")
@click.argument("odb_in", required=True, nargs=1)
def cli(output_odb, output_def, input_lef, diode_cell, diode_pin, threshold, max_pins, odb_in):
    db = odb.dbDatabase.create()
    odb.read_db(db, odb_in)
    block = db.getChip().getBlock()
    dbu = block.getDbUnitsPerMicron()
    master = db.findMaster(diode_cell)
    if master is None:
        eprint(f"Diode cell {diode_cell} not found.")
        raise SystemExit(1)
    width = master.getWidth()

    # the spare rows: nothing but fill / tie / decap cells on them
    def is_fill(inst):
        n = inst.getMaster().getName().lower()
        return "fill" in n or "tie" in n or "cap" in n

    logic_y = set()
    fills_by_y = {}
    for inst in block.getInsts():
        y = inst.getLocation()[1]
        if is_fill(inst):
            fills_by_y.setdefault(y, []).append(inst)
        else:
            logic_y.add(y)
    spare = [r for r in block.getRows() if r.getBBox().yMin() not in logic_y]
    if not spare:
        eprint("No spare row (a row with fill cells only): set TOP_SPARE_ROWS.")
        raise SystemExit(1)
    spare.sort(key=lambda r: r.getBBox().yMin())
    taken = {r.getBBox().yMin(): [] for r in spare}       # the diodes placed, x intervals per row
    removed_fill = 0

    def protected(net):
        return any(it.getInst().getMaster().getName() == diode_cell for it in net.getITerms())

    candidates = []
    for net in block.getNets():
        if net.isSpecial():
            continue
        iterms = net.getITerms()
        if len(iterms) == 0 or len(iterms) > max_pins or protected(net):
            continue
        pts = []
        for it in iterms:
            b = it.getInst().getBBox()
            pts.append(((b.xMin() + b.xMax()) / 2, (b.yMin() + b.yMax()) / 2))
        for bt in net.getBTerms():
            for bp in bt.getBPins():
                b = bp.getBBox()
                pts.append(((b.xMin() + b.xMax()) / 2, (b.yMin() + b.yMax()) / 2))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        span = (max(xs) - min(xs)) + (max(ys) - min(ys))
        if span / dbu < threshold:
            continue
        candidates.append((net, (min(xs) + max(xs)) / 2, span / dbu))

    candidates.sort(key=lambda c: c[1])
    placed = skipped = 0
    for i, (net, cx, span) in enumerate(candidates):
        done = False
        for row in spare:
            bb = row.getBBox()
            site_w = row.getSite().getWidth()
            x = min(max(int(cx - width / 2), bb.xMin()), bb.xMax() - width)
            x = bb.xMin() + round((x - bb.xMin()) / site_w) * site_w
            ivs = taken[bb.yMin()]
            moved = True
            while moved:
                moved = False
                for (a, b) in ivs:
                    if x < b and x + width > a:          # overlap: slide right past it
                        x = bb.xMin() + -(-(b - bb.xMin()) // site_w) * site_w
                        moved = True
            if x + width > bb.xMax():
                continue
            # the fill cells under the diode's footprint go; FillInsertion refills
            for f in list(fills_by_y.get(bb.yMin(), [])):
                fb = f.getBBox()
                if fb.xMin() < x + width and fb.xMax() > x:
                    fills_by_y[bb.yMin()].remove(f)
                    odb.dbInst_destroy(f)
                    removed_fill += 1
            inst = odb.dbInst_create(block, master, f"ANTENNA_NET_{i}")
            inst.setOrient(row.getOrient())
            inst.setLocation(x, bb.yMin())
            inst.setPlacementStatus("PLACED")
            inst.findITerm(diode_pin).connect(net)
            ivs.append((x, x + width))
            placed += 1
            done = True
            break
        if not done:
            eprint(f"[WARNING] no room in the spare rows for a diode on {net.getName()} ({span:.0f} um)")
            skipped += 1
    eprint(f"Placed {placed} antenna diode(s) in {len(spare)} spare row(s) for nets over {threshold} um with up to {max_pins} pins, replacing {removed_fill} fill cell(s); {skipped} without room.")
    if odb.write_db(db, output_odb) != 1:
        eprint("Failed to write output ODB file.")
        raise SystemExit(1)
    if output_def is not None and odb.write_def(block, output_def) != 1:
        eprint("Failed to write output DEF file.")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
