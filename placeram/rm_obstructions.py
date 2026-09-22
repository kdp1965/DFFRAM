# -*- coding: utf8 -*-
"""
Remove every routing obstruction from a design database.

DFFRAM's placer obstructs the route-through channels of the IHP CFGMEM
macros on the layers the parent design is meant to use (see
Placer.obstruct_channels); once the macro's own detailed routing is done
those obstructions have served their purpose and must not reach the
abstract views, so this script drops them.  Same command line as placeram
so the DFFRAM flow can run it as an odbpy step.
"""
import click
import odb

from .util import eprint


@click.command()
@click.option("-o", "--output-odb", required=True)
@click.option("--output-def", type=str, required=False, default=None)
@click.option("-l", "--input-lef", default=[], multiple=True, type=str, help="ignored")
@click.argument("odb_in", required=True, nargs=1)
def cli(output_odb, output_def, input_lef, odb_in):
    db = odb.dbDatabase.create()
    odb.read_db(db, odb_in)
    block = db.getChip().getBlock()
    obstructions = list(block.getObstructions())
    for o in obstructions:
        odb.dbObstruction_destroy(o)
    eprint("Removed %i routing obstruction(s)." % len(obstructions))
    if odb.write_db(db, output_odb) != 1:
        eprint("Failed to write output ODB file.")
        raise SystemExit(1)
    if output_def is not None and odb.write_def(block, output_def) != 1:
        eprint("Failed to write output DEF file.")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
