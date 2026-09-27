# DFFRAM needs LibreLane and the EDA tools, which come from the Nix shell in
# ./shell.nix. When `make` is run outside that shell, each recipe is re-run
# inside it automatically (nix-shell sets IN_NIX_SHELL).
ifeq ($(IN_NIX_SHELL),)
NIX_RUN = nix-shell --run
else
NIX_RUN = sh -c
endif

cfgmem16:
	$(NIX_RUN) "python3 dffram.py -b cfgmem 16x32"

left:
	$(NIX_RUN) "python3 dffram.py -b cfgmem_left --left 16x32"

# IHP SG13CMOS5L (ihp-sg13cmos5l PDK, sg13cmos5l_stdcell library). The PDK is
# not in ciel: it must be installed under $PDK_ROOT/ihp-sg13cmos5l (see Readme).
cfgmem16_cmos5l:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp 16x32"

left_cmos5l:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left 16x32"

# Bottom-edge data pins on Metal4 (the tile's under-used vertical layer)
# instead of Metal2, dodging the power stripes.  M4_PINS selects them:
# the Do0 pins by default, `M4_PINS='^D[io]0\\['` for Di0 as well.
M4_PINS ?= ^Do0\\[
cfgmem16_cmos5l_m4:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_PINS)' 16x32"

left_cmos5l_m4:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' 16x32"

# Route-through channels: four 8-site (3.84 um) decap columns through the
# array, before bits 6, 13, 19 and 26, with the macro's own routing kept off
# Metal2 and Metal4 there, so the tile's router gets continuous vertical
# tracks to hop between the Metal3 openings inside the macro.
CHANNELS ?= 6,13,19,26
cfgmem16_cmos5l_ch:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS)' 16x32"

left_cmos5l_ch:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS)' 16x32"

# Second iteration: two channels, one right after the first latch column
# (before bit 1) and one after the array (before the decoder column), the
# obstruction over the full macro height and the bottom-edge pins moved out
# of the channel spans (DFFRAM.PinsAvoidChannels).
CHANNELS2 ?= 1,32
cfgmem16_cmos5l_ch2:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS2)' 16x32"

left_cmos5l_ch2:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS2)' 16x32"

# Third iteration: the four channels of the first at half width (4 sites,
# 1.92 um: they were lightly used at 8), with the second iteration's
# full-height obstruction and pin avoidance.
CHANNELS3 ?= 6,13,19,26
CHANNEL_SITES3 ?= 4
cfgmem16_cmos5l_ch3:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS3)' --channel-sites $(CHANNEL_SITES3) 16x32"

left_cmos5l_ch3:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS3)' --channel-sites $(CHANNEL_SITES3) 16x32"

# Fifth arrangement: a full-width (8-site) channel right after the first
# latch column, and the three channels before bits 13, 19 and 26 at half
# width (4 sites); full-height obstruction and pin avoidance as before.
CHANNELS5 ?= 1:8,13:4,19:4,26:4
cfgmem16_cmos5l_ch5:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS5)' 16x32"

left_cmos5l_ch5:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS5)' 16x32"

# Left macro, sixth arrangement: the three channels before bits 6, 13 and
# 19 at half width, and a full-width channel after the last latch column
# (index 32 = between the array and the decoder region).
CHANNELS6L ?= 6:4,13:4,19:4,32:8
left_cmos5l_ch6:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_PINS)' --channels '$(CHANNELS6L)' 16x32"

# Seventh arrangement: the inspected channels (ch5 right / ch6 left) with
# every data pin on Metal4 (Di0 as well as Do0) and, on the right macro,
# the EN0 / A0 / BYP control pins on the W side face beside WE0 / WROW,
# as the left macro already has them.  Nothing of the macro's then reaches
# the mouth on Metal2.
M4_ALL ?= ^D[io]0\\[
cfgmem16_cmos5l_ch7:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_ALL)' --channels '$(CHANNELS5)' 16x32"

left_cmos5l_ch7:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_ALL)' --channels '$(CHANNELS6L)' 16x32"

# Eighth arrangement: as the seventh, but the channel obstruction is Metal2
# only.  With Metal4 obstructed too the channel's Metal4 ladder meets the
# tile's stripe via pads at the macro top and bottom edges (three fixed
# VGND shorts at the left column's first channel in every ch7 run); on
# Metal2 alone the ladder is what the router actually used anyway.
cfgmem16_cmos5l_ch8:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_ALL)' --channels '$(CHANNELS5)' -c CHANNEL_LAYERS=Metal2 16x32"

left_cmos5l_ch8:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_ALL)' --channels '$(CHANNELS6L)' -c CHANNEL_LAYERS=Metal2 16x32"

# No-channel A/B partner of the eighth arrangement (2026-09-23): the ch9
# pin arrangement (every data pin on Metal4, the right macro's controls on
# its side face) with no route-through channels at all, so the macro keeps
# every power rail.  Tile runs against ch9 isolate what the channels add.
cfgmem16_cmos5l_m4all:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp --pins-to-metal4 '$(M4_ALL)' 16x32"

left_cmos5l_m4all:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left --left --pins-to-metal4 '$(M4_ALL)' 16x32"

# CFGMEM_IHP_LEFT16_SRAM (2026-09-26): the ch8 left macro (every data pin on
# Metal4, Metal2-only route-through channels) for one spot, the band
# layout's CFGMEMS_LEFT[1].cfgmem_lo at (132.47, 619.92) N above SRAM[1]
# (RM_IHPSG13_1P_512x32 at x 3.36).  Its Metal4 rails sit on the SRAM's
# supply columns instead of the 44.96 um grid: every other pair of both
# bit-cell arrays (phased to the grid's own pairs), the periphery band's
# leftmost and rightmost pair (as ch9 had them), and the grid pair past the
# SRAM's east edge - 24 rails, the SRAM ones 2.81 um wide like the parent's
# SRAM stripes.  So the parent's full-height SRAM stripes run through the
# macro on its own rails, and the Metal4 pins keep 0.6 um from them.  The
# list comes from
#   python3 scripts/sram_aligned_stripes.py --sram-lef <PDK>/libs.ref/sg13cmos5l_sram/lef/RM_IHPSG13_1P_512x32_c2_bm_bist.lef \
#       --sram-x 3.36 --macro-x 132.47 --macro-width 340.32
# (rerun it for another spot).  CHANNELS6L's channels before bits 6, 13 and
# 19 would sit on the rails at 61.19, 130.13 and 191.95 um, where pdngen
# drops a rail whose via stacks land in the obstruction; they move one bit
# column off the rails (5, 14, 18), keeping the macro 340.32 um wide.
CHANNELS_SRAM ?= 5:4,14:4,18:4,32:8
SRAM_STRIPES ?= VPWR:11.435:2.81,VGND:17.055:2.81,VPWR:33.915:2.81,VGND:39.535:2.81,VGND:61.185:2.81,VPWR:66.335:2.81,VPWR:92.085:2.81,VGND:97.235:2.81,VPWR:124.505:2.81,VGND:130.125:2.81,VPWR:146.985:2.81,VGND:152.605:2.81,VPWR:169.465:2.81,VGND:175.085:2.81,VPWR:191.945:2.81,VGND:197.565:2.81,VPWR:214.425:2.81,VGND:220.045:2.81,VPWR:236.905:2.81,VGND:242.525:2.81,VPWR:259.385:2.81,VGND:265.005:2.81,VPWR:326.16:2.1,VGND:331.78:2.1
left_cmos5l_sram:
	$(NIX_RUN) "python3 dffram.py --manual-pdk -p ihp-sg13cmos5l -s sg13cmos5l_stdcell -b cfgmem_ihp_left_sram --left --pins-to-metal4 '$(M4_ALL)' --channels '$(CHANNELS_SRAM)' -c CHANNEL_LAYERS=Metal2 --pdn-stripes '$(SRAM_STRIPES)' 16x32"

# IHP SG13G2 (ihp-sg13g2 PDK, sg13g2_stdcell library). Same models and design
# names as CMOS5L, so the outputs go to build/ihp-sg13g2 and products/ihp-sg13g2.
# Tiny Tapeout 5x4 sg13g2 tile variant (../ihp-sg13g2-janestreet-prism): data
# pins on Metal4, power rails on the tile's 38.87 um TopMetal1 stripe grid for
# a LEFT16 column at x 2.88 and an IHP16 column at x 737.76 (see tech.yml).
cfgmem16_sg13g2_m4:
	$(NIX_RUN) "python3 dffram.py -p ihp-sg13g2 -s sg13g2_stdcell -b cfgmem_ihp --build-dir build/ihp-sg13g2 --products-dir products/ihp-sg13g2 --pins-to-metal4 '$(M4_PINS)' -c PDN_VOFFSET=$(IHP16_VOFFSET) 16x32"

left_sg13g2_m4:
	$(NIX_RUN) "python3 dffram.py -p ihp-sg13g2 -s sg13g2_stdcell -b cfgmem_ihp_left --left --build-dir build/ihp-sg13g2 --products-dir products/ihp-sg13g2 --pins-to-metal4 '$(M4_PINS)' -c PDN_VOFFSET=$(LEFT16_VOFFSET) 16x32"

IHP16_VOFFSET  ?= 15.81
LEFT16_VOFFSET ?= 12.16

cfgmem16_sg13g2:
	$(NIX_RUN) "python3 dffram.py -p ihp-sg13g2 -s sg13g2_stdcell -b cfgmem_ihp --build-dir build/ihp-sg13g2 --products-dir products/ihp-sg13g2 16x32"

left_sg13g2:
	$(NIX_RUN) "python3 dffram.py -p ihp-sg13g2 -s sg13g2_stdcell -b cfgmem_ihp_left --left --build-dir build/ihp-sg13g2 --products-dir products/ihp-sg13g2 16x32"

# Verilator regression of the CFGMEM16 macros (RTL and any built netlists);
# see verification/cfgmem/README.md.
test-cfgmem:
	$(NIX_RUN) "make -C verification/cfgmem all"

# Tile-level trial: one CFGMEM_IHP16 inside a Tiny Tapeout 2x2 CMOS5L tile,
# programmed over SPI (see tile_trial/). test-tile simulates the tile RTL.
tile-trial:
	$(NIX_RUN) "cd tile_trial && python3 flow.py"

test-tile:
	$(NIX_RUN) "make -C tile_trial/tb run"

all: dist

.PHONY: dist
dist: venv/manifest.txt
	./venv/bin/python3 setup.py sdist bdist_wheel

.PHONY: lint
lint: venv/manifest.txt
	./venv/bin/black --check .
	./venv/bin/flake8 .

venv: venv/manifest.txt
venv/manifest.txt: ./requirements_dev.txt
	rm -rf venv
	python3 -m venv ./venv
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade pip
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade wheel
	PYTHONPATH= ./venv/bin/python3 -m pip install --upgrade\
		-r ./requirements_dev.txt
	PYTHONPATH= ./venv/bin/python3 -m pip freeze > $@
	touch venv/manifest.txt

.PHONY: veryclean
veryclean: clean
veryclean:
	rm -rf venv/

.PHONY: clean
clean:
	rm -rf build/
	rm -rf logs/
	rm -rf dist/
	rm -rf *.egg-info
