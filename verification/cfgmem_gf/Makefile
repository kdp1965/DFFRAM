# Icarus bench for the CFGMEM8x44 (models/cfgmem_gf) on gf180mcu_fd_sc_mcu7t5v0.
#   make rtl                      the model through the block definitions and the PDK cell models
#   make nl NL=<...pnl.v>         a routed netlist (power pins)
PDK_ROOT ?= $(HOME)/projects/fossi/pdk_ll314
CELLS    := $(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog
ROOT     := ../..
IVL      := iverilog -g2012 -DFUNCTIONAL -DSIM '-DUNIT_DELAY=\#1'
NL       ?= $(ROOT)/products_gf_cfg/CFGMEM8x44/pnl/CFGMEM8x44.pnl.v

.PHONY: rtl nl clean
rtl:
	$(IVL) -o obj_rtl.vvp $(CELLS)/primitives.v $(CELLS)/gf180mcu_fd_sc_mcu7t5v0.v \
	    $(ROOT)/platforms/gf180mcuD/gf180mcu_fd_sc_mcu7t5v0/block_definitions.v \
	    $(ROOT)/models/cfgmem_gf/model.v tb_cfgmem8x44.v
	vvp -n obj_rtl.vvp

nl:
	$(IVL) -DUSE_POWER_PINS -DPOWER_PINS -o obj_nl.vvp $(CELLS)/primitives.v $(CELLS)/gf180mcu_fd_sc_mcu7t5v0.v \
	    $(NL) tb_cfgmem8x44.v
	vvp -n obj_nl.vvp

clean:
	rm -f obj_*.vvp
