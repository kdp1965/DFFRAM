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
