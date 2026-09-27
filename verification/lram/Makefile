# Verilator regression for the LRAM_IHP16x8 latch RAM macro.
#
#   make            run every target whose sources exist
#   make rtl-ihp    RTL model (models/lram_ihp, sg13g2 block definitions)
#   make nl-cmos5l  gate-level netlist from products/ (ihp-sg13cmos5l)
#   make nl-sg13g2  gate-level netlist from products/ihp-sg13g2/
#   make rtl-ihp-left / nl-cmos5l-left   the same for the west-pin variant
#                   LRAM_IHP_LEFT16x8 (models/lram_ihp_left)
#
# SEED=<n> OPS=<n> select the random seed / number of random cycles,
# TRACE=1 writes obj_<target>/tb_lram.vcd.  The cell models are shared
# with the CFGMEM bench (../cfgmem/models).
ROOT      := ../..
VERILATOR ?= verilator
SEED      ?= 1
OPS       ?= 5000
TRACE     ?= 0
PLUSARGS  := +seed=$(SEED) +ops=$(OPS) $(if $(filter 1,$(TRACE)),+trace,)

VFLAGS := --cc --exe --build -j 0 --trace \
          --top-module tb_lram \
          --x-initial unique --x-assign unique \
          -Wno-fatal -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM \
          -Wno-PINCONNECTEMPTY -Wno-PINMISSING -Wno-MULTIDRIVEN

BENCH  := tb_lram.v tb_lram.cpp
CELLS  := ../cfgmem/models
EAST   := -DLRAM=LRAM_IHP16x8
WEST   := -DLRAM=LRAM_IHP_LEFT16x8 -I$(ROOT)/models/lram_ihp_left

IHP_BD    := $(ROOT)/platforms/ihp-sg13g2/sg13g2_stdcell/block_definitions.v
IHP_RTL   := $(IHP_BD) $(ROOT)/models/lram_ihp/model.v
IHP_RTL_W := $(IHP_BD) $(ROOT)/models/lram_ihp_left/model.v
NL_CMOS5L := $(ROOT)/products/LRAM_IHP16x8/nl/LRAM_IHP16x8.nl.v
NL_CMOS5L_W := $(ROOT)/products/LRAM_IHP_LEFT16x8/nl/LRAM_IHP_LEFT16x8.nl.v
NL_SG13G2 := $(ROOT)/products/ihp-sg13g2/LRAM_IHP16x8/nl/LRAM_IHP16x8.nl.v

AVAILABLE := rtl-ihp rtl-ihp-left \
             $(if $(wildcard $(NL_CMOS5L)),nl-cmos5l,) \
             $(if $(wildcard $(NL_CMOS5L_W)),nl-cmos5l-left,) \
             $(if $(wildcard $(NL_SG13G2)),nl-sg13g2,)

.PHONY: all clean rtl-ihp rtl-ihp-left nl-cmos5l nl-cmos5l-left nl-sg13g2
all: $(AVAILABLE)

# $(1) = target name, $(2) = -D name define (+ include path), $(3) = design sources
define run_sim
	@echo "=== $(1) ==="
	$(VERILATOR) $(VFLAGS) --Mdir obj_$(1) -o sim $(2) $(3) $(BENCH) > obj_$(1).build.log 2>&1 \
	    || { tail -30 obj_$(1).build.log; exit 1; }
	@grep -c "%Warning" obj_$(1).build.log | sed 's/^/    verilator warnings: /' || true
	cd obj_$(1) && ./sim $(PLUSARGS)
endef

rtl-ihp:
	$(call run_sim,$@,$(EAST),$(CELLS)/sg13g2_cells.v $(IHP_RTL))

rtl-ihp-left:
	$(call run_sim,$@,$(WEST),$(CELLS)/sg13g2_cells.v $(IHP_RTL_W))

nl-sg13g2:
	$(call run_sim,$@,$(EAST),$(CELLS)/sg13g2_cells.v $(NL_SG13G2))

$(CELLS)/sg13cmos5l_cells.v: $(CELLS)/sg13g2_cells.v
	$(MAKE) -C ../cfgmem models/sg13cmos5l_cells.v

nl-cmos5l: $(CELLS)/sg13cmos5l_cells.v
	$(call run_sim,$@,$(EAST),$(CELLS)/sg13cmos5l_cells.v $(NL_CMOS5L))

nl-cmos5l-left: $(CELLS)/sg13cmos5l_cells.v
	$(call run_sim,$@,$(WEST),$(CELLS)/sg13cmos5l_cells.v $(NL_CMOS5L_W))

clean:
	rm -rf obj_*
