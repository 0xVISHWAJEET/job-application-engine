"""
Bridge into the vendored career-ops Node subsystem (vendor/career-ops/),
whose scan-ats-full.mjs walks public ATS-vendor company directories
(Greenhouse, Lever, Ashby, Workday, iCIMS, BambooHR, Paylocity, join.com -
~8,000+ companies per vendor) filtered by portals.yml's title_filter, zero
LLM tokens, pure HTTP+JSON. This is the single biggest portal-coverage
addition over discover_jobs.py's own sources (RemoteOK/WWR/web3.career/
Dice/Remotive/Wellfound/BuiltIn/GitJobs/JustJoinIT/LinkedIn + ~30 curated
ATS boards) - it reaches companies well beyond that curated list, with no
scraping workaround or bot-detection bypass (confirmed: pure directory +
public API walk).

Runs the Node scanner as a subprocess and parses its two output streams:
  - stdout: one JSON summary object for the whole run
  - stderr: one `{"kind":"offer",...}` line per kept posting (plus
    human-readable progress noise, which this module ignores)

Usage (standalone):
    python3 career_ops_bridge.py --since 14 --ats greenhouse,lever,ashby

As a library (used by discover_jobs.py):
    from career_ops_bridge import discover_via_career_ops
    listings = discover_via_career_ops(classify_role_fn, max_age_days=30)
"""

import json
import subprocess
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).parent.parent / "vendor" / "career-ops"
ATS_SOURCES = ["greenhouse", "lever", "ashby", "workday", "icims", "bamboohr", "paylocity", "join"]

# Keep each ATS sweep bounded so a single discover run finishes in minutes,
# not hours - scan-ats-full.mjs checkpoints every 500 companies and
# --resume can continue a capped run later via the CLI entrypoint directly.
DEFAULT_LIMIT_PER_ATS = 600


def _run_scanner(since_days: int, ats: list[str], limit_per_ats: int) -> tuple[dict, list[dict]]:
    """Runs scan-ats-full.mjs once across the given ATS sources and returns
    (summary_dict, offers_list). Raises if the vendored checkout is missing
    or node is unavailable - callers should catch and treat it as "this
    source produced nothing", same as any other discover_*() failure."""
    if not VENDOR_DIR.exists():
        raise FileNotFoundError(f"career-ops not vendored at {VENDOR_DIR} - run scripts/setup_career_ops.sh first")

    cmd = [
        "node", "scan-ats-full.mjs",
        "--json",
        "--since", str(since_days),
        "--ats", ",".join(ats),
        "--limit", str(limit_per_ats),
    ]
    proc = subprocess.run(
        cmd, cwd=VENDOR_DIR, capture_output=True, text=True, timeout=1800,
    )

    offers = []
    for line in proc.stderr.splitlines():
        start = line.find("{")
        if start < 0:
            continue
        try:
            ev = json.loads(line[start:])
        except (json.JSONDecodeError, ValueError):
            continue
        if ev.get("kind") == "offer" and ev.get("url") and ev.get("company") and ev.get("title"):
            offers.append(ev)

    summary = {}
    if proc.stdout.strip():
        try:
            summary = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, ValueError):
            pass

    return summary, offers


def discover_via_career_ops(
    classify_role_fn,
    max_age_days: int = 30,
    ats: list[str] | None = None,
    limit_per_ats: int = DEFAULT_LIMIT_PER_ATS,
) -> list[dict]:
    """Returns listings in the same shape discover_jobs.py's other
    discover_*() functions use: {portal, title, company, role_category,
    location, apply_url, posted_date, description}. `description` is left
    empty - discover_jobs.py's existing per-portal description-fetch
    fallback (main()'s "didn't carry a description from the search page"
    branch) fills it in for any portal name starting with "CareerOps:",
    the same way it already does for Wellfound/BuiltIn/GitJobs."""
    ats = ats or ATS_SOURCES
    try:
        summary, offers = _run_scanner(max_age_days, ats, limit_per_ats)
    except Exception as exc:
        print(f"  career-ops bridge: scan failed ({exc})", file=sys.stderr)
        return []

    if summary.get("stoppedByOutage"):
        print("  career-ops bridge: run stopped by outage breaker (partial results kept)", file=sys.stderr)

    listings = []
    for offer in offers:
        title = offer.get("title", "")
        category = classify_role_fn(title)
        if not category:
            continue  # portals.yml's own title_filter already narrowed this,
            # but classify_role_fn applies our role_category taxonomy for the
            # dashboard/scoring step, so an edge-case title_filter hit that
            # doesn't map to one of our categories is dropped here instead.
        listings.append({
            "portal": f"CareerOps:{offer.get('source', '?')}",
            "title": title,
            "company": offer.get("company", ""),
            "role_category": category,
            "location": offer.get("location") or "Unspecified",
            "apply_url": offer["url"],
            "posted_date": offer.get("postedAt"),
            "description": "",
        })
    return listings


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Standalone career-ops ATS scan (no scoring/tailoring)")
    parser.add_argument("--since", type=int, default=14)
    parser.add_argument("--ats", default=",".join(ATS_SOURCES))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT_PER_ATS)
    args = parser.parse_args()

    summary, offers = _run_scanner(args.since, args.ats.split(","), args.limit)
    print(json.dumps({"summary": summary, "offer_count": len(offers)}, indent=2))
    for o in offers[:20]:
        print(f"  {o['title']} @ {o['company']} ({o.get('source')}) - {o['url']}")


if __name__ == "__main__":
    main()
