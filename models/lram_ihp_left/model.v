/*
    Copyright 2026 Ken Pettit

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
*/

// LRAM_IHP_LEFT16x8: the west-pin variant of LRAM_IHP16x8.  Same netlist
// (models/lram_ihp/model.v under this name); the placer mirrors the rows
// (placeram/ihp_lram_data.py, --left) and pin_order.cfg puts every pin on
// the W edge.  A flipped (FN) instance of the east-pin macro cannot stand
// in for it: mirroring reverses the VPWR / VGND rail pair against the
// parent's stripe pairs, so the rails keep their offsets here instead
// (VPWR 11.44 + 44.96k, VGND 17.06 + 44.96k from the macro origin).

`define LRAM_TOP LRAM_IHP_LEFT16x8
`include "../lram_ihp/model.v"
