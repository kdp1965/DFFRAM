# KLayout batch script: rectangles covering everything drawn on the given
# layers of a GDS (wires, via pads, pins, power shapes), merged, with gaps
# narrower than `gap` (um) closed. Used by DFFRAM.WriteAbstractLEF.
#
#   klayout -b -r route_through_obs.py -rd gds=... -rd top=... \
#       -rd layers=Metal3=30/0[,met4=71/20] -rd gap=0.5 -rd out=obs.json
import json
import pya

ly = pya.Layout()
ly.read(gds)
cell = ly.cell(top) if top else ly.top_cell()
dbu = ly.dbu
radius = int(round(float(gap) / 2 / dbu))
result = {}
for spec in layers.split(","):
    name, ld = spec.split("=")
    layer, datatype = (int(v) for v in ld.split("/"))
    region = pya.Region(cell.begin_shapes_rec(ly.layer(layer, datatype)))
    region.merge()
    if radius > 0:
        region.size(radius)
        region.merge()
        region.size(-radius)
        region.merge()
    rects = []
    for poly in region.each():
        for piece in poly.decompose_trapezoids():
            b = piece.bbox()
            rects.append([b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu])
    result[name] = rects
with open(out, "w") as f:
    json.dump(result, f)
print("route_through_obs:", {k: len(v) for k, v in result.items()})
