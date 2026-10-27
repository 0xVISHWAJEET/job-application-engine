#!/usr/bin/env bash
# Re-provisions vendor/career-ops/node_modules (gitignored) on a fresh
# checkout. The vendored career-ops source itself is committed; your
# portals.yml (personal - your own target-role filter) and node_modules
# are not, since this repo is meant to be cloned and reused by anyone.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d vendor/career-ops ]; then
  echo "vendor/career-ops is missing entirely - re-clone it from" >&2
  echo "https://github.com/career-ops-hq/career-ops and remove its .git/ dir" >&2
  echo "before committing (see the integration note at the top of career_ops_bridge.py)." >&2
  exit 1
fi

cd vendor/career-ops
echo "Installing career-ops Node dependencies (production only, with Playwright Chromium for its CV/PDF tooling)..."
npm install --omit=dev --no-audit --no-fund
echo "Done. Verify with: node doctor.mjs --json"
