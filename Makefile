# (SheepFox) Firefox — Unified Build & Configuration Makefile
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.

PYTHON ?= python3

.PHONY: help build-configs check test install-dry-run install fetch-source patch-source build-browser clean

help:
	@echo "(SheepFox) Firefox — Project Commands"
	@echo "======================================"
	@echo "Config Suite (Drop-in for Stock Firefox):"
	@echo "  make build-configs     Compile modular configs into config/user.js & config/autoconfig/sheepfox.cfg"
	@echo "  make check             Verify compiled configs are in sync with modules"
	@echo "  make test              Run automated validation tests (JS prefs, policies, mozconfigs, patches)"
	@echo "  make install-dry-run   Preview profile & policy installation on current system"
	@echo "  make install           Apply SheepFox configs to detected Firefox profile"
	@echo ""
	@echo "Custom Fork Build (Compile SheepFox from Upstream Source):"
	@echo "  make fetch-source      Download & verify pinned Firefox upstream source tarball"
	@echo "  make patch-source      Apply SheepFox patches, branding, and default policies to source tree"
	@echo "  make build-browser     Compile optimized SheepFox binary (Cross-LTO + PGO)"
	@echo "  make clean             Remove temporary build caches"

build-configs:
	$(PYTHON) build/scripts/build-configs.py

check:
	$(PYTHON) build/scripts/build-configs.py --check

test:
	$(PYTHON) -m unittest discover -s tests -v

install-dry-run:
	$(PYTHON) scripts/install.py --dry-run

install:
	$(PYTHON) scripts/install.py

fetch-source:
	bash build/scripts/fetch-source.sh

patch-source:
	bash build/scripts/apply-patches.sh

build-browser:
	bash build/scripts/build-browser.sh

clean:
	rm -rf __pycache__ tests/__pycache__ .pytest_cache
