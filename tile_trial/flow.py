#!/usr/bin/env python3
"""
Harden the CFGMEM tile trial with LibreLane's Classic flow plus one extra
step that runs the tile's Metal4 power stripes across the macro.

    python3 flow.py [run-tag]      (inside the nix shell, PDK_ROOT set)
"""
import json
import os
import sys

from decimal import Decimal
from typing import List, Optional, Tuple

from librelane.config import Variable
from librelane.flows.classic import Classic
from librelane.steps import OpenROAD
from librelane.steps.odb import OdbpyStep

HERE = os.path.dirname(os.path.abspath(__file__))


class ExtendPowerStripes(OdbpyStep):
    id = "Tile.ExtendPowerStripes"
    name = "Extend Power Stripes Over Macros"

    def get_script_path(self):
        return os.path.join(HERE, "odb_stripes.py")


class AddPlacementBlockages(OdbpyStep):
    id = "Tile.AddPlacementBlockages"
    name = "Add Placement Blockages"

    config_vars = OdbpyStep.config_vars + [
        Variable(
            "TILE_PLACEMENT_BLOCKAGES",
            Optional[List[Tuple[Decimal, Decimal, Decimal, Decimal]]],
            "Regions (llx, lly, urx, ury in microns) kept free of standard cells.",
        ),
    ]

    def get_script_path(self):
        return os.path.join(HERE, "odb_blockages.py")

    def get_command(self):
        cmd = super().get_command()
        for region in self.config["TILE_PLACEMENT_BLOCKAGES"] or []:
            cmd += ["--region", " ".join(str(v) for v in region)]
        return cmd


class TileFlow(Classic):
    Steps = list(Classic.Steps)
    Steps.insert(Steps.index(OpenROAD.GeneratePDN) + 1, ExtendPowerStripes)
    Steps.insert(Steps.index(OpenROAD.GlobalPlacementSkipIO), AddPlacementBlockages)


def main():
    # usage: flow.py [run-tag] [config.json] [--no-stripes]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_stripes = "--no-stripes" in sys.argv
    config_path = args[1] if len(args) > 1 else os.path.join(HERE, "config.json")
    with open(config_path, encoding="utf8") as f:
        cfg = json.load(f)
    if no_stripes:
        TileFlow.Steps = [s for s in TileFlow.Steps if s is not ExtendPowerStripes]
    pdk_root = os.environ["PDK_ROOT"]
    cfg["PDK"] = "ihp-sg13cmos5l"
    cfg["STD_CELL_LIBRARY"] = "sg13cmos5l_stdcell"
    # The pinned PDK's KLayout DRC deck checks nothing; use the dev-branch deck
    # when the checkout described in the Readme is present.
    dev_drc = os.path.join(
        pdk_root, "ihp-open-pdk-dev", "ihp-sg13cmos5l",
        "libs.tech", "klayout", "tech", "drc", "ihp-sg13cmos5l.drc",
    )
    if os.path.exists(dev_drc):
        cfg["KLAYOUT_DRC_RUNSET"] = dev_drc
    else:
        print("dev-branch KLayout DRC deck not found; skipping KLayout DRC")
        cfg["RUN_KLAYOUT_DRC"] = False

    flow = TileFlow(cfg, design_dir=HERE, pdk_root=pdk_root)
    flow.start(tag=args[0] if args else None)


if __name__ == "__main__":
    main()
