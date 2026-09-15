# Verilator regression for the CFGMEM16 configuration memory macros.
#
#   make            run every target whose sources exist
#   make rtl-ihp    IHP RTL model (models/cfgmem_ihp*, sg13g2 block definitions)
#   make nl-cmos5l  gate-level netlists from products/ (ihp-sg13cmos5l)
#   make nl-sg13g2  gate-level netlists from products/ihp-sg13g2/
#   make rtl-sky130 sky130 RTL model (models/cfgmem*, sky130 block definitions)
#   make nl-sky130  gate-level netlists from products/ (sky130A)
#
# SEED=<n> OPS=<n> select the random seed / number of random operations,
# TRACE=1 writes obj_<target>/tb_cfgmem.vcd.
ROOT      := ../..
VERILATOR ?= verilator
SEED      ?= 1
OPS       ?= 2000
TRACE     ?= 0
PLUSARGS  := +seed=$(SEED) +ops=$(OPS) $(if $(filter 1,$(TRACE)),+trace,)

VFLAGS := --cc --exe --build -j 0 --trace \
          --top-module tb_cfgmem_pair \
          --x-initial unique --x-assign unique \
          -Wno-fatal -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL -Wno-UNUSEDPARAM \
          -Wno-PINCONNECTEMPTY -Wno-PINMISSING -Wno-MULTIDRIVEN

BENCH := tb_cfgmem_pair.v tb_cfgmem.cpp

IHP_BD    := $(ROOT)/platforms/ihp-sg13g2/sg13g2_stdcell/block_definitions.v
IHP_RTL   := $(IHP_BD) $(ROOT)/models/cfgmem_ihp/model.v $(ROOT)/models/cfgmem_ihp_left/model.v
NL_CMOS5L := $(ROOT)/products/CFGMEM_IHP16/nl/CFGMEM_IHP16.nl.v $(ROOT)/products/CFGMEM_IHP_LEFT16/nl/CFGMEM_IHP_LEFT16.nl.v
NL_SG13G2 := $(ROOT)/products/ihp-sg13g2/CFGMEM_IHP16/nl/CFGMEM_IHP16.nl.v $(ROOT)/products/ihp-sg13g2/CFGMEM_IHP_LEFT16/nl/CFGMEM_IHP_LEFT16.nl.v
SKY_BD    := $(ROOT)/platforms/sky130A/sky130_fd_sc_hd/block_definitions.v
SKY_RTL   := $(SKY_BD) $(ROOT)/models/cfgmem/model.v $(ROOT)/models/cfgmem_left/model.v
NL_SKY    := $(ROOT)/products/CFGMEM16/nl/CFGMEM16.nl.v $(ROOT)/products/CFGMEM_LEFT16/nl/CFGMEM_LEFT16.nl.v

IHP_NAMES := -DCFGMEM_RIGHT=CFGMEM_IHP16 -DCFGMEM_LEFT=CFGMEM_IHP_LEFT16
SKY_NAMES := -DCFGMEM_RIGHT=CFGMEM16 -DCFGMEM_LEFT=CFGMEM_LEFT16

# Run the targets whose sources are present.
AVAILABLE := rtl-ihp rtl-sky130 \
             $(if $(wildcard $(NL_CMOS5L)),nl-cmos5l,) \
             $(if $(wildcard $(NL_SG13G2)),nl-sg13g2,) \
             $(if $(wildcard $(NL_SKY)),nl-sky130,)

.PHONY: all clean rtl-ihp nl-cmos5l nl-sg13g2 rtl-sky130 nl-sky130
all: $(AVAILABLE)

# $(1) = target name, $(2) = -D name defines, $(3) = design sources
define run_sim
	@echo "=== $(1) ==="
	$(VERILATOR) $(VFLAGS) --Mdir obj_$(1) -o sim $(2) $(3) $(BENCH) > obj_$(1).build.log 2>&1 \
	    || { tail -30 obj_$(1).build.log; exit 1; }
	@grep -c "%Warning" obj_$(1).build.log | sed 's/^/    verilator warnings: /' || true
	cd obj_$(1) && ./sim $(PLUSARGS)
endef

rtl-ihp:
	$(call run_sim,$@,$(IHP_NAMES),models/sg13g2_cells.v $(IHP_RTL))

nl-sg13g2:
	$(call run_sim,$@,$(IHP_NAMES),models/sg13g2_cells.v $(NL_SG13G2))

# sg13cmos5l is the sg13g2 library under another prefix.
models/sg13cmos5l_cells.v: models/sg13g2_cells.v
	sed 's/sg13g2_/sg13cmos5l_/g' $< > $@

nl-cmos5l: models/sg13cmos5l_cells.v
	$(call run_sim,$@,$(IHP_NAMES),models/sg13cmos5l_cells.v $(NL_CMOS5L))

rtl-sky130:
	$(call run_sim,$@,$(SKY_NAMES),models/sky130_cells.v $(SKY_RTL))

nl-sky130:
	$(call run_sim,$@,$(SKY_NAMES),models/sky130_cells.v $(NL_SKY))

clean:
	rm -rf obj_* models/sg13cmos5l_cells.v
