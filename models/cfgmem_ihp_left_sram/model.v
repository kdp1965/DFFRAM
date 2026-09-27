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

// CFGMEM_IHP_LEFT16_SRAM: CFGMEM_IHP_LEFT16 (models/cfgmem_ihp_left, same
// netlist and pins) for one fixed spot above an IHP 1P SRAM.  Its Metal4
// rails sit on the SRAM's own supply columns instead of the regular 44.96 um
// grid, so the parent's full-height SRAM stripes run through the macro on
// its rails and none of them has to dodge a pin (Makefile target
// left_cmos5l_sram, --pdn-stripes).

`define CFGMEM_LEFT_TOP CFGMEM_IHP_LEFT16_SRAM
`include "../cfgmem_ihp_left/model.v"
