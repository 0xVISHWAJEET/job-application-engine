#!/usr/bin/env bash
# Compiles a resume .tex file to PDF using TinyTeX (already installed at
# ~/.TinyTeX, not on PATH by default). Run twice - the resume template uses
# \pageref{LastPage} in its footer, which needs a second pass to resolve
# once the .aux file exists.
#
# Usage:
#   ./compile.sh                                  # compiles ../../vishwajeet.tex -> ../../vishwajeet.pdf
#   ./compile.sh /path/to/tailored_acme.tex        # compiles a specific file, PDF alongside it
set -euo pipefail

# Absolute path, not $HOME-relative: this script also runs inside Docker
# (tailor_cv.py needs beautifulsoup4, which isn't installed on the host -
# see discover_jobs.py/backfill_tailor.py's docker run invocations), where
# the process runs as root and $HOME resolves to /root, not
# /home/aspirez - silently pointing at a pdflatex that was never there.
PDFLATEX="/home/aspirez/.TinyTeX/bin/x86_64-linux/pdflatex"
if [ ! -x "$PDFLATEX" ]; then
    echo "pdflatex not found at $PDFLATEX - is TinyTeX installed? (if running in Docker, is /home/aspirez/.TinyTeX mounted?)" >&2
    exit 1
fi

TEX_FILE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/vishwajeet.tex}"

if [ ! -f "$TEX_FILE" ]; then
    echo "No such file: $TEX_FILE" >&2
    exit 1
fi

TEX_DIR="$(cd "$(dirname "$TEX_FILE")" && pwd)"
TEX_NAME="$(basename "$TEX_FILE")"

cd "$TEX_DIR"
"$PDFLATEX" -interaction=nonstopmode -halt-on-error "$TEX_NAME" > /tmp/resume_compile.log 2>&1 || {
    echo "First pass failed - see /tmp/resume_compile.log" >&2
    tail -30 /tmp/resume_compile.log >&2
    exit 1
}
"$PDFLATEX" -interaction=nonstopmode -halt-on-error "$TEX_NAME" > /tmp/resume_compile.log 2>&1 || {
    echo "Second pass failed - see /tmp/resume_compile.log" >&2
    tail -30 /tmp/resume_compile.log >&2
    exit 1
}

PDF_FILE="${TEX_NAME%.tex}.pdf"
echo "Compiled: $TEX_DIR/$PDF_FILE"
