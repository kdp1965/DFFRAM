# Verilator bench for the tile RTL with the CFGMEM_IHP16 RTL model.
ROOT   := ../..
CFG    := $(ROOT)/verification/cfgmem
SRC    := $(ROOT)/tile_trial/src/tt_um_cfgmem_trial.v \
          $(ROOT)/platforms/ihp-sg13cmos5l/sg13cmos5l_stdcell/block_definitions.v \
          $(ROOT)/models/cfgmem_ihp/model.v \
          $(CFG)/models/sg13cmos5l_cells.v
VFLAGS := --cc --exe --build -j 0 --top-module tt_um_cfgmem_trial -Wno-fatal -Wno-DECLFILENAME -Wno-UNUSEDSIGNAL

all: run
$(CFG)/models/sg13cmos5l_cells.v:
	$(MAKE) -C $(CFG) models/sg13cmos5l_cells.v
run: $(CFG)/models/sg13cmos5l_cells.v
	verilator $(VFLAGS) --Mdir obj_dir -o sim $(SRC) tb_tile.cpp > build.log 2>&1 || { tail -20 build.log; exit 1; }
	@grep -c "%Warning" build.log | sed 's/^/    verilator warnings: /' || true
	cd obj_dir && ./sim
clean:
	rm -rf obj_dir build.log
