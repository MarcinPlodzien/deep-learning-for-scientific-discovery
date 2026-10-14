#!/usr/bin/env bash
# Build the website: prepare slides and notebooks from the lecture folders,
# then render the site into ./docs (which GitHub Pages serves).
set -euo pipefail
cd "$(dirname "$0")"
echo "[1/2] Preparing slides and notebooks..."
python3 prep_site.py
echo "[2/2] Rendering site into ./docs ..."
quarto render
echo "Done. The website is in ./docs (open ./docs/index.html)."
