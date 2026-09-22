#! python3
# -*- coding: utf8 -*-
# Copyright ©2020-2023 The American University in Cairo
# Copyright ©2023 Efabless Corporation
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
import os
import re
import json
import math
from typing import Dict, List, Optional, Tuple
from fnmatch import fnmatch
from decimal import Decimal

import yaml
import cloup
from librelane.common import mkdirp, Path
from librelane.config import Variable
from librelane.logging import info, warn, err
from librelane.state import DesignFormat
from librelane.flows import SequentialFlow, cloup_flow_opts, Flow
from librelane.flows.classic import Classic
from librelane.steps import Step, Yosys, OpenROAD, Magic, KLayout, Netgen, Odb, Checker, Misc

from librelane.steps import OpenROAD

class PlaceRAM(Odb.OdbpyStep):
    id = "DFFRAM.PlaceRAM"

    config_vars = [
        Variable(
            "RAM_SIZE",
            str,
            "The size of the RAM macro being hardened the format {words}x{bits}",
        ),
        Variable(
            "BUILDING_BLOCKS",
            str,
            "The set of building blocks being used.",
            default="ram",
        ),
        Variable(
            "LEFT",
            bool,
            "Set true to generate a left-hand macro",
        ),
        Variable(
            "CHANNELS",
            Optional[str],
            "Route-through channels of the IHP CFGMEM placer: comma-separated bit "
            "indices before which a decap channel is placed in every array row, "
            "obstructed on CHANNEL_LAYERS for the macro's own routing.",
            default=None,
        ),
        Variable(
            "CHANNEL_SITES",
            int,
            "Width of each route-through channel in sites.",
            default=8,
        ),
        Variable(
            "CHANNEL_LAYERS",
            str,
            "Layers obstructed over the route-through channels.",
            default="Metal2,Metal4",
        ),
    ]

    def get_script_path(self):
        return "placeram"

    def get_command(self) -> List[str]:
        if self.config["LEFT"]:
            raw = super().get_command() + [
                "--building-blocks",
                f"{self.config['PDK']}:{self.config['STD_CELL_LIBRARY']}:{self.config['BUILDING_BLOCKS']}",
                "--size",
                self.config["RAM_SIZE"],
                "--left",
            ]
        else:
            raw = super().get_command() + [
                "--building-blocks",
                f"{self.config['PDK']}:{self.config['STD_CELL_LIBRARY']}:{self.config['BUILDING_BLOCKS']}",
                "--size",
                self.config["RAM_SIZE"],
            ]
        if self.config["CHANNELS"]:
            raw += [
                "--channels",
                self.config["CHANNELS"],
                "--channel-sites",
                str(self.config["CHANNEL_SITES"]),
                "--channel-layers",
                self.config["CHANNEL_LAYERS"],
            ]
        raw.insert(raw.index("placeram"), "-m")
        print(f'RAW COMMAND: {raw}')
        return raw


class RemoveChannelObstructions(Odb.OdbpyStep):
    """Drops the route-through channel obstructions the placer created,
    once the macro's detailed routing is done (see placeram/rm_obstructions.py)."""

    id = "DFFRAM.RemoveChannelObstructions"
    name = "Remove Channel Obstructions"

    def get_script_path(self):
        return "placeram.rm_obstructions"

    def get_command(self) -> List[str]:
        raw = super().get_command()
        raw.insert(raw.index("placeram.rm_obstructions"), "-m")
        return raw


class Floorplan(OpenROAD.Floorplan):
    id = "DFFRAM.Floorplan"

    outputs = [
        DesignFormat.ODB,
    ]

    config_vars = [
        var
        for var in OpenROAD.Floorplan.config_vars
        if var.name not in ["FP_SIZING", "CORE_AREA", "DIE_AREA"]
    ] + [
        Variable(
            "HORIZONTAL_HALO",
            type=Decimal,
            description="The space between the horizontal edges of the die area and the core area in microns.",
            units="µm",
            default=2.5,
        ),
        Variable(
            "VERTICAL_HALO",
            type=Decimal,
            description="The space between the vertical edges of the die area and the core area in microns.",
            units="µm",
            default=2.5,
        ),
        Variable(
            "MINIMUM_HEIGHT",
            type=Decimal,
            description="A minimum height to be applied",
            default=0,
            units="µm",
        ),
    ]

    def run(self, state_in, **kwargs):
        min_height = self.config["MINIMUM_HEIGHT"]

        core_width = Decimal(
            state_in.metrics.get("dffram__suggested__core_width") or 20000
        )
        core_height = Decimal(
            state_in.metrics.get("dffram__suggested__core_height") or 20000
        )

        horizontal_halo = self.config["HORIZONTAL_HALO"]
        vertical_halo = self.config["VERTICAL_HALO"]

        pdk = self.config["PDK"]
        scl = self.config["STD_CELL_LIBRARY"]

        tech_info_path = os.path.join(".", "platforms", pdk, scl, "tech.yml")
        tech_info = yaml.safe_load(open(tech_info_path))
        site_info = tech_info.get("site")

        site_width = Decimal(1)
        site_height = Decimal(1)

        if site_info is not None:
            site_width = Decimal(site_info["width"])
            site_height = Decimal(site_info["height"])

            horizontal_halo = math.ceil(horizontal_halo / site_width) * site_width
            vertical_halo = math.ceil(vertical_halo / site_height) * site_height
        else:
            if horizontal_halo != 0.0 or vertical_halo != 0.0:
                warn(
                    "Note: This platform does not have site information. The halo will not be rounded up to the nearest number of sites. This may cause off-by-one issues with some tools."
                )

        die_width = core_width + horizontal_halo * 2
        die_height = core_height + vertical_halo * 2
        if die_height < min_height:
            die_height = min_height
            vertical_halo = (die_height - core_height) / 2
            vertical_halo = math.ceil(vertical_halo / site_height) * site_height

        kwargs, env = self.extract_env(kwargs)

        env["DIE_AREA"] = f"0 0 {die_width} {die_height}"
        env[
            "CORE_AREA"
        ] = f"{horizontal_halo} {vertical_halo} {horizontal_halo + core_width} {vertical_halo + core_height}"
        env["FP_SIZING"] = "absolute"
        return super().run(state_in, env=env, **kwargs)


Rect = Tuple[float, float, float, float]


def _rect_minus(rect: Rect, hole: Rect) -> List[Rect]:
    """Subtract `hole` from `rect`, returning up to four rectangles."""
    x0, y0, x1, y1 = rect
    hx0, hy0, hx1, hy1 = hole
    if hx0 >= x1 or hx1 <= x0 or hy0 >= y1 or hy1 <= y0:
        return [rect]
    out: List[Rect] = []
    if hy1 < y1:
        out.append((x0, hy1, x1, y1))
    if hy0 > y0:
        out.append((x0, y0, x1, hy0))
    my0, my1 = max(y0, hy0), min(y1, hy1)
    if hx0 > x0:
        out.append((x0, my0, hx0, my1))
    if hx1 < x1:
        out.append((hx1, my0, x1, my1))
    return out


def _lef_pin_rects(lef_text: str) -> Dict[str, List[Rect]]:
    """Pin rectangles per layer from a LEF macro."""
    rects: Dict[str, List[Rect]] = {}
    for _, body in re.findall(r"^\s*PIN (\S+)(.*?)^\s*END \1\s*$", lef_text, re.S | re.M):
        layer = None
        for line in body.splitlines():
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "LAYER":
                layer = parts[1]
            elif parts[0] == "RECT" and layer is not None:
                rects.setdefault(layer, []).append(
                    tuple(float(v) for v in parts[1:5])  # type: ignore
                )
    return rects


def merge_route_through_lef(
    base_lef: str,
    new_obs: Dict[str, List[Rect]],
    out_lef: str,
    layers: List[str],
    pin_clearance: float,
) -> Dict[str, Tuple[int, float]]:
    """
    Copy `base_lef` (Magic's abstract: pins plus hidden, bounding-box
    obstructions) to `out_lef`, replacing the OBS entries of `layers` with the
    rectangles in `new_obs` (the drawn geometry of those layers), kept
    `pin_clearance` away from same-layer pins.

    Returns, per layer, the number of rectangles written and the fraction of
    the macro area they cover.
    """
    base = open(base_lef, encoding="utf8").read()
    size = re.search(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", base)
    macro_area = float(size.group(1)) * float(size.group(2)) if size else 1.0

    pins = _lef_pin_rects(base)
    width = float(size.group(1)) if size else 0.0
    height = float(size.group(2)) if size else 0.0
    stats: Dict[str, Tuple[int, float]] = {}
    replacement: Dict[str, List[Rect]] = {}
    for layer in layers:
        rects = new_obs.get(layer, [])
        for px0, py0, px1, py1 in pins.get(layer, []):
            # Clearance outside the macro and along the pin's sides, but none
            # towards the macro interior: the pin's own wire continues there
            # and has to stay an obstruction, or the router lays a same-net
            # wire a few nanometres from metal it cannot see (an M3.b
            # spacing violation on the tile, 2026-09-15).
            eps = 1e-3
            on_west, on_east = px0 <= eps, px1 >= width - eps
            on_south, on_north = py0 <= eps, py1 >= height - eps
            hole = (
                px0 if on_east else px0 - pin_clearance,
                py0 if on_north else py0 - pin_clearance,
                px1 if on_west else px1 + pin_clearance,
                py1 if on_south else py1 + pin_clearance,
            )
            rects = [piece for r in rects for piece in _rect_minus(r, hole)]
        replacement[layer] = rects
        area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in rects)
        stats[layer] = (len(rects), area / macro_area)

    obs_match = re.search(r"^(\s*)OBS\s*$(.*?)^\s*END\s*$", base, re.S | re.M)
    if obs_match is None:
        raise ValueError(f"No OBS section found in {base_lef}")
    indent = obs_match.group(1)
    kept: List[str] = []
    layer = None
    for line in obs_match.group(2).splitlines():
        parts = line.split()
        if parts and parts[0] == "LAYER":
            layer = parts[1]
        if layer in replacement:
            continue  # dropped: rewritten below
        kept.append(line)
    rewritten = "\n".join(kept).rstrip("\n")
    for layer, rects in replacement.items():
        rewritten += f"\n{indent}   LAYER {layer} ;"
        for x0, y0, x1, y1 in rects:
            rewritten += f"\n{indent}      RECT {x0:.3f} {y0:.3f} {x1:.3f} {y1:.3f} ;"
    new_text = (
        base[: obs_match.start()]
        + f"{indent}OBS"
        + rewritten
        + f"\n{indent}END"
        + base[obs_match.end():]
    )
    with open(out_lef, "w", encoding="utf8") as f:
        f.write(new_text)
    return stats


def _def_layer_map(path: str) -> Dict[str, Tuple[int, int]]:
    """LEF layer name -> (GDS layer, datatype) of its drawn (NET) shapes."""
    result: Dict[str, Tuple[int, int]] = {}
    for line in open(path, encoding="utf8"):
        parts = line.split()
        if len(parts) == 4 and "NET" in parts[1].split(",") and parts[0] not in result:
            try:
                result[parts[0]] = (int(parts[2]), int(parts[3]))
            except ValueError:
                pass
    return result


_KLAYOUT_LAYER_MAP_VAR = next(
    v for v in KLayout.KLayoutStep.config_vars if v.name == "KLAYOUT_DEF_LAYER_MAP"
)


class WriteAbstractLEF(Step):
    """
    Rewrites the macro's abstract LEF so that, on selected layers, the
    obstructions follow the drawn geometry of the GDS (wires, via pads, power
    shapes) instead of covering the whole macro. The top level can then route
    through the unused tracks of those layers. Pins and the remaining layers
    are taken unchanged from Magic's LEF.
    """

    id = "DFFRAM.WriteAbstractLEF"
    name = "Route-Through Abstract LEF"

    inputs = [DesignFormat.GDS, DesignFormat.LEF]
    outputs = [DesignFormat.LEF]

    config_vars = [
        _KLAYOUT_LAYER_MAP_VAR,
        Variable(
            "LEF_ROUTE_THROUGH_LAYERS",
            Optional[List[str]],
            "Layers whose obstructions in the macro LEF follow the drawn "
            "geometry instead of Magic's hidden bounding box. Unset keeps "
            "Magic's abstract unchanged.",
        ),
        Variable(
            "LEF_ROUTE_THROUGH_GAP",
            Decimal,
            "Gaps between shapes narrower than this are obstructed as well, so "
            "the parent router is not offered slots it cannot use.",
            units="µm",
            default=0.5,
        ),
        Variable(
            "LEF_ROUTE_THROUGH_PIN_CLEARANCE",
            Decimal,
            "Clearance kept between the rewritten obstructions and pins on the same layer.",
            units="µm",
            default=0.3,
        ),
    ]

    def run(self, state_in, **kwargs):
        layers = self.config["LEF_ROUTE_THROUGH_LAYERS"] or []
        if not layers:
            info("LEF_ROUTE_THROUGH_LAYERS is unset: keeping the Magic abstract LEF.")
            return {}, {}

        layer_map = _def_layer_map(str(self.config["KLAYOUT_DEF_LAYER_MAP"]))
        missing = [layer for layer in layers if layer not in layer_map]
        if missing:
            raise ValueError(f"Layers {missing} not found in {self.config['KLAYOUT_DEF_LAYER_MAP']}")
        spec = ",".join(f"{layer}={layer_map[layer][0]}/{layer_map[layer][1]}" for layer in layers)

        design = self.config["DESIGN_NAME"]
        obs_json = os.path.join(self.step_dir, "obstructions.json")
        script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "scripts", "klayout", "route_through_obs.py"
        )
        self.run_subprocess(
            [
                "klayout", "-b", "-r", script,
                "-rd", f"gds={state_in[DesignFormat.GDS]}",
                "-rd", f"top={design}",
                "-rd", f"layers={spec}",
                "-rd", f"gap={self.config['LEF_ROUTE_THROUGH_GAP']}",
                "-rd", f"out={obs_json}",
            ],
            log_to=os.path.join(self.step_dir, "klayout.log"),
        )
        with open(obs_json, encoding="utf8") as f:
            new_obs = {layer: [tuple(r) for r in rects] for layer, rects in json.load(f).items()}

        out_lef = os.path.join(self.step_dir, f"{design}.lef")
        stats = merge_route_through_lef(
            str(state_in[DesignFormat.LEF]),
            new_obs,
            out_lef,
            layers,
            float(self.config["LEF_ROUTE_THROUGH_PIN_CLEARANCE"]),
        )
        for layer, (count, coverage) in stats.items():
            info(
                f"{layer}: {count} obstruction rectangles covering "
                f"{coverage * 100:.0f}% of the macro (rest is open for routing)."
            )
        return {DesignFormat.LEF: Path(out_lef)}, {}


GATED_RUN_VARS = [
    "RUN_MAGIC_STREAMOUT",
    "RUN_KLAYOUT_STREAMOUT",
    "RUN_MAGIC_WRITE_LEF",
    "RUN_MAGIC_DRC",
    "RUN_KLAYOUT_DRC",
    "RUN_KLAYOUT_XOR",
    "RUN_LVS",
    "RUN_FILL_INSERTION",
    "RUN_SPEF_EXTRACTION",
    "RUN_MCSTA",
    "RUN_IRDROP_REPORT",
]


@Flow.factory.register()
@Step.factory.register()
class PinsToLayer(Odb.OdbpyStep):
    """
    Moves the bottom-edge shapes of selected pins to another vertical layer
    (scripts/odbpy/pins_to_layer.py), dodging that layer's power stripes.
    A no-op unless PINS_TO_LAYER_REGEX is set.
    """

    id = "DFFRAM.PinsToLayer"
    name = "Pins to Layer"

    config_vars = [
        Variable(
            "PINS_TO_LAYER_REGEX",
            Optional[str],
            "Pins (regex) whose bottom-edge shapes move from IO_PIN_V_LAYER to "
            "PINS_TO_LAYER.  Unset leaves the pins as placed.",
        ),
        Variable(
            "PINS_TO_LAYER",
            str,
            "Layer the selected pins are moved to.",
            default="Metal4",
        ),
        Variable(
            "PINS_TO_LAYER_FROM",
            str,
            "Layer the selected pins are on before the move (the vertical pin layer).",
            default="Metal2",
        ),
        Variable(
            "PINS_TO_LAYER_CLEARANCE",
            Decimal,
            "Spacing kept from power stripes and other pins on that layer.",
            units="µm",
            default=0.3,
        ),
    ]

    def get_script_path(self):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "scripts", "odbpy", "pins_to_layer.py"
        )

    def get_command(self) -> List[str]:
        return super().get_command() + [
            "--pins", self.config["PINS_TO_LAYER_REGEX"],
            "--layer", self.config["PINS_TO_LAYER"],
            "--from-layer", self.config["PINS_TO_LAYER_FROM"],
            "--clearance", str(self.config["PINS_TO_LAYER_CLEARANCE"]),
        ]

    def run(self, state_in, **kwargs):
        if not self.config["PINS_TO_LAYER_REGEX"]:
            info("PINS_TO_LAYER_REGEX is unset: pins left as placed.")
            return {}, {}
        return super().run(state_in, **kwargs)


class DFFRAM(SequentialFlow):
    Steps = [
        Yosys.Synthesis,
        Misc.LoadBaseSDC,
        OpenROAD.STAPrePNR,
        Floorplan,
        PlaceRAM,
        Floorplan,
        PlaceRAM,
        OpenROAD.IOPlacement,
        Odb.CustomIOPlacement,
        OpenROAD.GeneratePDN,
        PinsToLayer,
        OpenROAD.STAMidPNR,
        OpenROAD.GlobalRouting,

        OpenROAD.CheckAntennas,
#        OpenROAD.RepairDesignPostGRT,
        Odb.DiodesOnPorts,
        Odb.HeuristicDiodeInsertion,
        OpenROAD.RepairAntennas,

        OpenROAD.STAMidPNR,
        OpenROAD.DetailedRouting,
        RemoveChannelObstructions,
        Odb.RemoveRoutingObstructions,
        OpenROAD.CheckAntennas,
        Checker.TrDRC,
        Odb.ReportDisconnectedPins,
        Checker.DisconnectedPins,
        Odb.ReportWireLength,
        Checker.WireLength,
        OpenROAD.FillInsertion,
        OpenROAD.RCX,
        OpenROAD.STAPostPNR,
        OpenROAD.IRDropReport,
        Magic.StreamOut,
        KLayout.StreamOut,
        Magic.WriteLEF,
        WriteAbstractLEF,
        Odb.CheckDesignAntennaProperties,
        KLayout.StreamOut,
        KLayout.XOR,
        Checker.XOR,
        Magic.DRC,

        KLayout.DRC,

        Checker.MagicDRC,
        Magic.SpiceExtraction,
        Checker.IllegalOverlap,
        Netgen.LVS,
        Checker.LVS,
    ]

    # Same RUN_* switches as LibreLane's Classic flow, so a platform can
    # disable signoff tools it does not support via tech.yml `flow_config`.
    config_vars = [var for var in Classic.config_vars if var.name in GATED_RUN_VARS]

    gating_config_vars = {
        "Magic.StreamOut": ["RUN_MAGIC_STREAMOUT"],
        "KLayout.StreamOut": ["RUN_KLAYOUT_STREAMOUT"],
        "Magic.WriteLEF": ["RUN_MAGIC_WRITE_LEF"],
        "DFFRAM.WriteAbstractLEF": ["RUN_MAGIC_WRITE_LEF"],
        "Magic.DRC": ["RUN_MAGIC_DRC"],
        "Checker.MagicDRC": ["RUN_MAGIC_DRC"],
        "KLayout.DRC": ["RUN_KLAYOUT_DRC"],
        "KLayout.XOR": [
            "RUN_KLAYOUT_XOR",
            "RUN_MAGIC_STREAMOUT",
            "RUN_KLAYOUT_STREAMOUT",
        ],
        "Checker.XOR": [
            "RUN_KLAYOUT_XOR",
            "RUN_MAGIC_STREAMOUT",
            "RUN_KLAYOUT_STREAMOUT",
        ],
        "Magic.SpiceExtraction": ["RUN_LVS"],
        "Checker.IllegalOverlap": ["RUN_LVS"],
        "Netgen.LVS": ["RUN_LVS"],
        "Checker.LVS": ["RUN_LVS"],
        "OpenROAD.FillInsertion": ["RUN_FILL_INSERTION"],
        "OpenROAD.RCX": ["RUN_SPEF_EXTRACTION"],
        "OpenROAD.STAPostPNR": ["RUN_MCSTA"],
        "OpenROAD.IRDropReport": ["RUN_IRDROP_REPORT"],
    }


@cloup.command()
@cloup.option("-b", "--building-blocks", default="ram")
@cloup.option("--left", is_flag=True)
@cloup.option(
    "-v", "--variant", default=None, help="Use design variants (such as 1RW1R)"
)
@cloup.option(
    "-C",
    "--clock-period",
    "default_clock_period",
    default=20,
    type=Decimal,
    help="Fallback clock period for STA (when unspecified by the platform)",
)
@cloup.option(
    "--horizontal-halo",
#    default=2.5,
    default=1.0,
    type=Decimal,
    help="Horizontal halo in µm",
)
@cloup.option(
    "--vertical-halo",
#    default=2.5,
    default=1.0,
    type=Decimal,
    help="Vertical halo in µm",
)
@cloup.option(
    "--build-dir",
    default="build",
    help="Directory under which per-design run directories are created",
)
@cloup.option(
    "--products-dir",
    default="products",
    help="Directory under which the final views of each design are saved",
)
@cloup.option(
    "-H",
    "--min-height",
    default=0.0,
    type=Decimal,
    help="Minimum height in µm",
)
@cloup.option(
    "--pins-to-metal4",
    default=None,
    help="Regex of pins whose bottom-edge shapes go on Metal4 instead of the "
    "vertical pin layer (routing then reaches Metal4 for pin access only)",
)
@cloup.option(
    "--channels",
    default=None,
    help="Route-through channels (IHP CFGMEM placer): comma-separated bit "
    "indices before which a decap channel is placed in every array row; the "
    "channel's Metal2/Metal4 tracks are left to the parent design's router",
)
@cloup.option(
    "--channel-sites",
    default=8,
    type=int,
    help="Width of each route-through channel in sites",
)
@cloup_flow_opts(accept_config_files=False)
@cloup.argument("size", default="32x32", nargs=1)
def main(
    pdk,
    scl,
    frm,
    to,
    skip,
    tag,
    last_run,
    with_initial_state,
    size,
    building_blocks,
    left,
    variant,
    horizontal_halo,
    vertical_halo,
    default_clock_period,
    min_height,
    pins_to_metal4,
    channels,
    channel_sites,
    build_dir,
    products_dir,
    flow_name,
    pdk_root,
    **kwargs,
):
    if variant == "DEFAULT":
        variant = None

    if scl is None:
        # Default to the platform's only standard cell library, if it has one.
        pdk_platforms = os.path.join(".", "platforms", pdk)
        libraries = (
            sorted(
                d
                for d in os.listdir(pdk_platforms)
                if os.path.isdir(os.path.join(pdk_platforms, d))
            )
            if os.path.isdir(pdk_platforms)
            else []
        )
        scl = libraries[0] if len(libraries) == 1 else "sky130_fd_sc_hd"
    platform = f"{pdk}:{scl}"

    bb_dir = os.path.join(".", "models", building_blocks)
    if not os.path.isdir(bb_dir):
        err(f"Generic building blocks {building_blocks} not found.")
        exit(os.EX_NOINPUT)

    pdk_dir = os.path.join(".", "platforms", pdk, scl)
    if not os.path.isdir(pdk_dir):
        err(f"Definitions for platform {platform} not found.")
        exit(os.EX_NOINPUT)

    block_definitions_used = os.path.join(pdk_dir, "block_definitions.v")
    bb_used = os.path.join(bb_dir, "model.v")
    platform_config_file = os.path.join(bb_dir, "config.yml")
    platform_config = yaml.safe_load(open(platform_config_file))

    pin_order_file = os.path.join(bb_dir, "pin_order.cfg")
    m = re.match(r"(\d+)x(\d+)", size)
    if m is None:
        err(f"Invalid RAM size '{size}'.")
        exit(os.EX_USAGE)

    words = int(m[1])
    word_width = int(m[2])
    word_width_bytes = word_width // 8

    if os.getenv("FORCE_ACCEPT_SIZE") != 1:
        if (
            words not in platform_config["counts"]
            or word_width not in platform_config["widths"]
        ):
            err("Size %s not supported by %s." % (size, building_blocks))
            exit(os.EX_USAGE)

        if variant not in platform_config["variants"]:
            err("Variant %s is unsupported by %s." % (variant, building_blocks))
            exit(os.EX_USAGE)

    variant_string = ("_%s" % variant) if variant is not None else ""
    design_name_template = platform_config["design_name_template"]
    design = os.getenv("FORCE_DESIGN_NAME") or design_name_template.format(
        **{
            "count": words,
            "width": word_width,
            "width_bytes": word_width_bytes,
            "variant": variant_string,
        }
    )

    build_dir = os.path.join(build_dir, design)
    mkdirp(build_dir)

    tech_info_path = os.path.join(".", "platforms", pdk, scl, "tech.yml")
    tech_info = yaml.safe_load(open(tech_info_path))

    clock_period = default_clock_period
    block_clock_periods = tech_info["sta"]["clock_periods"].get(building_blocks)
    if block_clock_periods is not None:
        for wildcard, period in block_clock_periods.items():
            if fnmatch(size, wildcard):
                clock_period = period
                break

    logical_width = word_width_bytes
    if building_blocks == "rf":
        logical_width = word_width

    rt_max_layer = tech_info["metal_layers"]["rt-max-layer"]

    # Platform-specific LibreLane settings (PDN pitch, tool switches, ...).
    # String values may reference environment variables such as $PDK_ROOT;
    # an absolute path that does not exist on this machine is dropped with a
    # warning so the platform stays usable without optional add-ons.
    platform_flow_config = {}
    for key, value in (tech_info.get("flow_config") or {}).items():
        if isinstance(value, str) and "$" in value:
            value = os.path.expandvars(value)
            if value.startswith("/") and not os.path.exists(value):
                warn(f"{key}: '{value}' not found, using the PDK default.")
                continue
        platform_flow_config[key] = value

    # Data pins on Metal4 (experiment): the router may use Metal4, but only
    # grudgingly (90% capacity reduction) so it reaches the pins and little
    # else, and whatever it does draw there becomes an obstruction in the
    # abstract instead of leaving Metal4 open.
    variant_config = {}
    if pins_to_metal4:
        through = list(platform_flow_config.get("LEF_ROUTE_THROUGH_LAYERS") or [])
        if "Metal4" not in through:
            through.append("Metal4")
        variant_config = {
            "PINS_TO_LAYER_REGEX": pins_to_metal4,
            "PINS_TO_LAYER": "Metal4",
            "PINS_TO_LAYER_FROM": tech_info["metal_layers"]["ver-layer"],
            "RT_MAX_LAYER": "Metal4",
            "GRT_LAYER_ADJUSTMENTS": [0, 0, 0, Decimal("0.9"), 0],
            "LEF_ROUTE_THROUGH_LAYERS": through,
        }

    if channels:
        variant_config["CHANNELS"] = channels
        variant_config["CHANNEL_SITES"] = channel_sites
    # LibreLane's own -c KEY=VALUE flow option (config_override_strings), e.g.
    # -c PDN_VOFFSET=12.16 to put the macro's power rails on a parent design's
    # stripe grid; numeric values become Decimals.
    for override in kwargs.pop("config_override_strings", None) or []:
        if "=" not in override:
            err(f"-c expects KEY=VALUE, got '{override}'")
            exit(os.EX_USAGE)
        key, value = override.split("=", 1)
        try:
            variant_config[key] = Decimal(value)
        except Exception:
            variant_config[key] = value

    TargetFlow = Flow.factory.get(flow_name) or DFFRAM
    dffram_flow = TargetFlow(
        {
            "DESIGN_NAME": design,
            "CLOCK_PORT": "CLK",
            "CLOCK_PERIOD": clock_period,
            "GPL_CELL_PADDING": 0,
            "DPL_CELL_PADDING": 0,
            "RT_MAX_LAYER": rt_max_layer,
            "GRT_ALLOW_CONGESTION": True,
            "PDK": pdk,
            "STD_CELL_LIBRARY": scl,
            "RAM_SIZE": size,
            "LEFT": left,
            "BUILDING_BLOCKS": building_blocks,
            "VERILOG_FILES": [
                block_definitions_used,
                bb_used,
            ],
            "SYNTH_ELABORATE_ONLY": True,
            "SYNTH_ELABORATE_FLATTEN": True,
            "SYNTH_READ_BLACKBOX_LIB": True,
            "SYNTH_EXCLUSION_CELL_LIST": "/dev/null",
            "SYNTH_PARAMETERS": [f"WSIZE={logical_width}"],
            "GRT_REPAIR_ANTENNAS": False,
            "MINIMUM_HEIGHT": min_height,
            "VERTICAL_HALO": vertical_halo,
            "HORIZONTAL_HALO": horizontal_halo,
            "CLOCK_PERIOD": clock_period,
            # IO Placement
            "FP_PIN_ORDER_CFG": pin_order_file,
            "FP_IO_VTHICKNESS_MULT": Decimal(2),
            "FP_IO_HTHICKNESS_MULT": Decimal(2),
            "FP_IO_HEXTEND": Decimal(0),
            "FP_IO_VEXTEND": Decimal(0),
            "FP_IO_VLENGTH": 2,
            "FP_IO_HLENGTH": 2,
            # PDN
            "DESIGN_IS_CORE": False,
            **platform_flow_config,
            **variant_config,
        },
        design_dir=os.path.abspath(build_dir),
        pdk_root=pdk_root,
    )

    final_state = dffram_flow.start(
        frm=frm,
        to=to,
        skip=skip,
        tag=tag,
        last_run=last_run,
        with_initial_state=with_initial_state,
    )

    mkdirp(products_dir)
    final_state.save_snapshot(os.path.join(products_dir, design))


if __name__ == "__main__":
    main()
