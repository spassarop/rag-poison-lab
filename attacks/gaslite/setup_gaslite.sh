#! /bin/sh
# Reconstruct the adapted GASLITE `repo/` from the versioned overlay + patches.
# `repo/` is an upstream clone and is NOT versioned in this repo; this script
# regenerates it deterministically.
#
# Run from attacks/gaslite/ :   bash setup_gaslite.sh
# Pin a commit (recommended):   GASLITE_COMMIT=<sha> bash setup_gaslite.sh
#
# Afterwards: create/activate the venv and install deps (see ../README.md §1),
# then build the dataset and run an attack (§2).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

GASLITE_URL="https://github.com/matanbt/GASLITE.git"
GASLITE_COMMIT="${GASLITE_COMMIT:-8dc7646f1ac8cd68f38463df01578c74fff22795}"   # set to the exact sha you validated

if [ ! -d repo/.git ]; then
  echo "[setup] cloning GASLITE -> repo/"
  git clone --recurse-submodules "$GASLITE_URL" repo
fi

if [ -n "$GASLITE_COMMIT" ]; then
  echo "[setup] checking out pinned commit $GASLITE_COMMIT"
  git -C repo checkout "$GASLITE_COMMIT"
  git -C repo submodule update --init --recursive
else
  echo "[setup] WARNING: GASLITE_COMMIT not set — using current default branch."
  echo "[setup] For reproducibility, re-run with GASLITE_COMMIT=<the sha below>."
fi

echo "[setup] copying overlay/ -> repo/  (added files: builders, _device.py, configs, scripts)"
cp -R overlay/. repo/

echo "[setup] applying idempotent patches to upstream sources"
python apply_gaslite_patches.py

RESOLVED="$(git -C repo rev-parse HEAD)"
echo ""
echo "[setup] DONE. GASLITE commit in use: $RESOLVED"
echo "[setup] Record this commit (and your seed/hardware) in repro/config.txt."
