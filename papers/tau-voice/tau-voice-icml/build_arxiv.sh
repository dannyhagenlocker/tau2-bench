#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARXIV_DIR="${SCRIPT_DIR}_arXiv"

rm -rf "$ARXIV_DIR"

arxiv_latex_cleaner "$SCRIPT_DIR" --config "$SCRIPT_DIR/cleaner_config.yaml"

rm -f "$ARXIV_DIR"/{UPDATE_STAT_SIG.md,cleaner_config.yaml}

cp "$SCRIPT_DIR/main.bbl" "$ARXIV_DIR/main.bbl"

echo "Done. Output: $ARXIV_DIR"
echo "To compile: cd $ARXIV_DIR && pdflatex -shell-escape main.tex && pdflatex -shell-escape main.tex"
