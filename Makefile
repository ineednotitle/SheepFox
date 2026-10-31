# ============================================================================
# (SheepFox) Zen browser — unified build & configuration entry points
# This Source Code Form is subject to the terms of the Mozilla Public License 2.0.
# ============================================================================

PYTHON ?= python3
TARGET ?= auto
SHEEPFOX_SRC ?= $(CURDIR)/mozbuild/firefox-src

.PHONY: help build-configs check test test-verbose install install-dry-run \
        installers installers-windows installers-macos \
        fetch-source patch-source build-browser clean verify

help:
	@echo "(SheepFox) Zen browser — Project Commands"
	@echo "=========================================="
	@echo "Drop-in config suite (works on Zen Browser and stock Firefox):"
	@echo "  make build-configs   Compile config/modules/*.js -> user.js + sheepfox.cfg"
	@echo "  make check           Verify the generated configs are in sync (CI gate)"
	@echo "  make test            Run the full verification suite"
	@echo "  make install         Apply SheepFox to the detected Zen Browser / Firefox profile"
	@echo "  make install-dry-run Preview every path that would be touched"
	@echo "  make installers      Build dist/SheepFox-Setup-*.exe + SheepFox-*.dmg + *.iso"
	@echo "                       (needs: pip install ziglang pycdlib)"
	@echo ""
	@echo "Custom fork build (compile (SheepFox) Zen browser from upstream Gecko source):"
	@echo "  make fetch-source    Download + SHA-512 verify the pinned Firefox source"
	@echo "  make patch-source    Inject branding/policies and apply patches/series"
	@echo "  make build-browser   ./mach configure && build && package  (TARGET=$(TARGET))"
	@echo "                       TARGET=linux-x86_64|linux-aarch64|windows-x86_64|macos-universal"
	@echo "                       SHEEPFOX_PGO=1 make build-browser   # two-stage PGO"
	@echo "  make clean           Remove caches and staged fork artifacts"
	@echo "  make verify          build-configs + check + test (what CI runs)"

build-configs:
	$(PYTHON) mozbuild/scripts/build-configs.py

check:
	$(PYTHON) mozbuild/scripts/build-configs.py --check

test:
	$(PYTHON) -m unittest discover -s tests -v

install:
	$(PYTHON) scripts/install.py

install-dry-run:
	$(PYTHON) scripts/install.py --dry-run

installers:
	$(PYTHON) mozbuild/scripts/build-installers.py

installers-windows:
	$(PYTHON) mozbuild/scripts/build-installers.py --windows

installers-macos:
	$(PYTHON) mozbuild/scripts/build-installers.py --macos

fetch-source:
	bash mozbuild/scripts/fetch-source.sh

patch-source:
	SHEEPFOX_SRC_DIR=$(SHEEPFOX_SRC) bash mozbuild/scripts/apply-patches.sh

build-browser:
	SHEEPFOX_SRC_DIR=$(SHEEPFOX_SRC) bash mozbuild/scripts/build-browser.sh --target $(TARGET)

verify: check test
	@echo "All SheepFox verification gates passed."

clean:
	rm -rf __pycache__ tests/__pycache__ .pytest_cache mozbuild/staging
	rm -f mozbuild/.last-objdir
