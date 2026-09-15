# Add placement blockages (regions where no standard cell may be placed).
# Used by the trial to keep the channels beside the macro empty so that,
# together with routing obstructions there, tile routes must cross the macro.
import click
import odb
from reader import click_odb


@click.command()
@click.option("--region", "regions", multiple=True, help="llx lly urx ury in microns")
@click_odb
def add(reader, regions):
    block = reader.block
    dbu = block.getDefUnits()
    for spec in regions:
        x0, y0, x1, y1 = (int(round(float(v) * dbu)) for v in spec.split())
        odb.dbBlockage_create(block, x0, y0, x1, y1)
        print(f"[INFO] placement blockage {x0/dbu} {y0/dbu} {x1/dbu} {y1/dbu}")
    print(f"[INFO] {len(regions)} placement blockages added")


if __name__ == "__main__":
    add()
