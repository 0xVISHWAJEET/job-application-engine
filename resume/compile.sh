#!/usr/bin/env bash
# Compiles a resume .tex file to PDF via pdflatex (TeX Live, or TinyTeX -
# https://yihui.org/tinytex/ - a lightweight installer if you don't already
# have a LaTeX distro). Run twice - the resume template uses
# \pageref{LastPage} in its footer, which needs a second pass to resolve
# once the .aux file exists.
#
# Usage:
#   ./compile.sh                                  # compiles ../profile/base_resume.tex
#   ./compile.sh /path/to/tailored_acme.tex        # compiles a specific file, PDF alongside it
set -euo pipefail

PDFLATEX="$(command -v pdflatex || true)"
if [ -z "$PDFLATEX" ]; then
    # Common TinyTeX install location, in case it's not on PATH yet.
    for candidate in "$HOME/.TinyTeX/bin/"*/pdflatex; do
        if [ -x "$candidate" ]; then
            PDFLATEX="$candidate"
            break
        fi
    done
fi
if [ -z "$PDFLATEX" ] || [ ! -x "$PDFLATEX" ]; then
    echo "pdflatex not found on PATH or at ~/.TinyTeX - install TeX Live (apt install texlive-latex-extra) or TinyTeX (https://yihui.org/tinytex/)." >&2
    exit 1
fi

TEX_FILE="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/profile/base_resume.tex}"

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
