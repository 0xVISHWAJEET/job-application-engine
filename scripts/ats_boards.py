"""
Discovery via the public JSON APIs that most tech/AI/crypto companies'
"careers" pages are actually built on (Greenhouse, Lever, Ashby). This is
the legitimate, unavoidable structured-data path for the AI-company and
blockchain-company career pages in URL.txt (openai.com/careers,
anthropic.com/careers, careers.near.org, etc.) - their public /careers
pages are JS-rendered shells, but the ATS vendor hosting the actual
postings exposes a plain JSON feed with no login and no bot-detection to
route around. Confirmed by direct probing (see README's portal-coverage
notes) rather than assumed from vendor docs.

Each entry in COMPANY_BOARDS is (company_display_name, ats_type, slug).
The slug is the ATS-specific board identifier, not always the company's
own domain name - verified per-company since guesses often 404.
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

COMPANY_BOARDS = [
    # AI companies (URL.txt lines 125-134)
    ("Anthropic", "greenhouse", "anthropic"),
    ("Scale AI", "greenhouse", "scaleai"),
    ("Stability AI", "greenhouse", "stabilityai"),
    ("Google DeepMind", "greenhouse", "deepmind"),
    ("Together AI", "greenhouse", "togetherai"),
    ("Mistral AI", "lever", "mistral"),
    ("OpenAI", "ashby", "openai"),
    ("Cohere", "ashby", "cohere"),
    # Blockchain/crypto companies (URL.txt lines 115-124)
    ("Coinbase", "greenhouse", "coinbase"),
    ("Consensys", "greenhouse", "consensys"),
    ("NEAR Foundation", "greenhouse", "nearfoundation"),
    ("Kraken", "ashby", "kraken"),
    ("Circle", "ashby", "circle"),
    ("Solana Labs", "ashby", "solanalabs"),
    # Large infra/platform companies that regularly hire DevOps/SRE/Platform
    ("Cloudflare", "greenhouse", "cloudflare"),
    ("Stripe", "greenhouse", "stripe"),
    ("Databricks", "greenhouse", "databricks"),
    ("GitLab", "greenhouse", "gitlab"),
    ("Snowflake", "ashby", "snowflake"),
    ("Elastic", "greenhouse", "elastic"),
    ("MongoDB", "greenhouse", "mongodb"),
    ("PagerDuty", "greenhouse", "pagerduty"),
    ("New Relic", "greenhouse", "newrelic"),
    ("Datadog", "greenhouse", "datadog"),
    ("Vercel", "greenhouse", "vercel"),
    # More AI companies
    ("Alchemy", "ashby", "alchemy"),
    ("Confluent", "ashby", "confluent"),
    ("xAI", "greenhouse", "xai"),
    ("ElevenLabs", "ashby", "elevenlabs"),
    ("Replit", "ashby", "replit"),
    ("Render", "ashby", "render"),
    # AI/ML infra
    ("SpaceX", "greenhouse", "spacex"),
    ("Palantir", "lever", "palantir"),
    ("Modal", "ashby", "modal"),
    ("Baseten", "ashby", "baseten"),
    ("LangChain", "ashby", "langchain"),
    ("Pinecone", "ashby", "pinecone"),
    ("Weaviate", "ashby", "weaviate"),
    ("Temporal", "ashby", "temporal"),
    # Data infra
    ("Cockroach Labs", "greenhouse", "cockroachlabs"),
    ("ClickHouse", "ashby", "clickhouse"),
    ("Airbyte", "ashby", "airbyte"),
    ("Fivetran", "greenhouse", "fivetran"),
    ("Supabase", "ashby", "supabase"),
    ("Neon", "ashby", "neon"),
    ("PlanetScale", "greenhouse", "planetscale"),
    # DevOps/Platform/dev-tools
    ("Railway", "ashby", "railway"),
    ("Porter", "lever", "porter"),
    ("Coder", "ashby", "coder"),
    ("CircleCI", "greenhouse", "circleci"),
    ("Buildkite", "greenhouse", "buildkite"),
    ("Honeycomb", "greenhouse", "honeycomb"),
    ("Sentry", "ashby", "sentry"),
    ("LaunchDarkly", "greenhouse", "launchdarkly"),
    ("Twilio", "greenhouse", "twilio"),
    ("Okta", "greenhouse", "okta"),
    ("WorkOS", "ashby", "workos"),
    ("Clerk", "ashby", "clerk"),
    ("1Password", "ashby", "1password"),
    # Security
    ("Wiz", "ashby", "wiz"),
    ("Snyk", "ashby", "snyk"),
    ("Semgrep", "ashby", "semgrep"),
    ("Chainguard", "greenhouse", "chainguard"),
    ("Sysdig", "lever", "sysdig"),
    ("Orca Security", "greenhouse", "orcasecurity"),
    # More blockchain/crypto
    ("Anchorage Digital", "lever", "anchorage"),
    ("Fireblocks", "greenhouse", "fireblocks"),
    ("Blockdaemon", "ashby", "blockdaemon"),
    ("QuickNode", "ashby", "quicknode"),
    ("OpenSea", "ashby", "opensea"),
    ("Magic Eden", "ashby", "magiceden"),
    ("Offchain Labs", "lever", "offchainlabs"),
    ("Celestia", "lever", "celestia"),
    ("Jump Crypto", "greenhouse", "jumpcrypto"),
    ("Phantom", "ashby", "phantom"),
    ("Zerion", "lever", "zerion"),
    ("Immutable", "lever", "immutable"),
    ("Animoca Brands", "lever", "animocabrands"),
    ("MoonPay", "lever", "moonpay"),
    ("Dune Analytics", "ashby", "dune"),
    # Fintech (still hires DevOps/security/platform roles)
    ("Deel", "ashby", "deel"),
    ("Brex", "greenhouse", "brex"),
    ("Ramp", "ashby", "ramp"),
    ("Linear", "ashby", "linear"),
    ("Plaid", "ashby", "plaid"),
    # Large general tech (still hires DevOps/SRE/Platform roles at volume)
    ("Discord", "greenhouse", "discord"),
    ("Instacart", "greenhouse", "instacart"),
    ("Robinhood", "greenhouse", "robinhood"),
    ("Airbnb", "greenhouse", "airbnb"),
    ("Lyft", "greenhouse", "lyft"),
    ("Reddit", "greenhouse", "reddit"),
    ("Helium", "greenhouse", "helium"),
    # More AI companies
    ("Inflection AI", "greenhouse", "inflectionai"),
    ("Hume AI", "greenhouse", "hume"),
    ("Cartesia", "ashby", "cartesia"),
    ("Deepgram", "ashby", "deepgram"),
    ("AssemblyAI", "greenhouse", "assemblyai"),
    ("Imbue", "greenhouse", "imbue"),
    ("Cresta", "greenhouse", "cresta"),
    ("Sierra", "ashby", "sierra"),
    ("Decagon", "ashby", "decagon"),
    ("Poolside", "ashby", "poolside"),
    # More blockchain/crypto
    ("Syndica", "ashby", "syndica"),
    ("Helius", "ashby", "helius"),
    ("LayerZero Labs", "greenhouse", "layerzerolabs"),
    ("Ethena Labs", "lever", "ethenalabs"),
    # Cloud-native/observability
    ("Nirmata", "greenhouse", "nirmata"),
    ("Grafana Labs", "greenhouse", "grafanalabs"),
    ("SigNoz", "ashby", "signoz"),
    # Web3 analytics/infra
    ("Tenderly", "ashby", "tenderly"),
    ("Nansen", "greenhouse", "nansen"),
    ("Messari", "greenhouse", "messari"),
    ("Figment", "greenhouse", "figment"),
    # AI/ML platform
    ("Anyscale", "ashby", "anyscale"),
    ("Cerebras", "ashby", "cerebras"),
    ("CoreWeave", "greenhouse", "coreweave"),
    # Devtools/media infra
    ("StackBlitz", "greenhouse", "stackblitz"),
    ("LiveKit", "ashby", "livekit"),
    ("Mux", "ashby", "mux"),
    ("Cloudinary", "lever", "cloudinary"),
]


def _fetch_json(url: str, timeout: int = 15) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _within_age(posted: datetime | None, max_age_days: int) -> bool:
    if posted is None:
        return True
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - posted).days <= max_age_days


def _classify(title: str, classify_fn) -> str | None:
    return classify_fn(title)


def discover_greenhouse(company: str, slug: str, classify_fn, max_age_days: int) -> list[dict]:
    listings = []
    try:
        data = _fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    except Exception as exc:
        print(f"  Greenhouse ({company}): fetch failed ({exc})", file=sys.stderr)
        return listings

    for job in data.get("jobs", []):
        title = job.get("title", "")
        category = classify_fn(title)
        if not category:
            continue

        posted = None
        raw_date = job.get("first_published") or job.get("updated_at")
        if raw_date:
            try:
                posted = datetime.fromisoformat(raw_date)
            except ValueError:
                pass
        if not _within_age(posted, max_age_days):
            continue

        from bs4 import BeautifulSoup
        description = BeautifulSoup(job.get("content", ""), "html.parser").get_text(separator="\n", strip=True)

        location = (job.get("location") or {}).get("name", "")
        listings.append({
            "portal": f"Greenhouse ({company})",
            "title": title,
            "company": company,
            "role_category": category,
            "location": location,
            "apply_url": job.get("absolute_url", ""),
            "posted_date": posted.date().isoformat() if posted else None,
            "description": description,
        })

    return listings


def discover_lever(company: str, slug: str, classify_fn, max_age_days: int) -> list[dict]:
    listings = []
    try:
        data = _fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    except Exception as exc:
        print(f"  Lever ({company}): fetch failed ({exc})", file=sys.stderr)
        return listings

    if not isinstance(data, list):
        return listings

    for job in data:
        title = job.get("text", "")
        category = classify_fn(title)
        if not category:
            continue

        posted = None
        created_ms = job.get("createdAt")
        if created_ms:
            try:
                posted = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            except (ValueError, OSError):
                pass
        if not _within_age(posted, max_age_days):
            continue

        from bs4 import BeautifulSoup
        description = BeautifulSoup(job.get("description", ""), "html.parser").get_text(separator="\n", strip=True)
        lists_text = "\n".join(
            item.get("text", "") + "\n" + BeautifulSoup(item.get("content", ""), "html.parser").get_text("\n", strip=True)
            for item in job.get("lists", [])
        )

        listings.append({
            "portal": f"Lever ({company})",
            "title": title,
            "company": company,
            "role_category": category,
            "location": (job.get("categories") or {}).get("location", ""),
            "apply_url": job.get("hostedUrl", ""),
            "posted_date": posted.date().isoformat() if posted else None,
            "description": (description + "\n" + lists_text).strip(),
        })

    return listings


def discover_ashby(company: str, slug: str, classify_fn, max_age_days: int) -> list[dict]:
    listings = []
    try:
        data = _fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    except Exception as exc:
        print(f"  Ashby ({company}): fetch failed ({exc})", file=sys.stderr)
        return listings

    for job in data.get("jobs", []):
        title = job.get("title", "")
        category = classify_fn(title)
        if not category:
            continue

        posted = None
        raw_date = job.get("publishedAt")
        if raw_date:
            try:
                posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                pass
        if not _within_age(posted, max_age_days):
            continue

        listings.append({
            "portal": f"Ashby ({company})",
            "title": title,
            "company": company,
            "role_category": category,
            "location": job.get("location", ""),
            "apply_url": job.get("jobUrl") or job.get("applyUrl", ""),
            "posted_date": posted.date().isoformat() if posted else None,
            "description": job.get("descriptionPlain", ""),
        })

    return listings


_DISCOVERERS = {
    "greenhouse": discover_greenhouse,
    "lever": discover_lever,
    "ashby": discover_ashby,
}


def discover_all_ats_boards(classify_fn, max_age_days: int = 30) -> list[dict]:
    """Runs every board in COMPANY_BOARDS and returns the combined, already
    role-filtered and age-filtered listing set."""
    listings = []
    for company, ats_type, slug in COMPANY_BOARDS:
        fn = _DISCOVERERS[ats_type]
        found = fn(company, slug, classify_fn, max_age_days)
        listings.extend(found)
        print(f"  {ats_type} ({company}): {len(found)} matching", file=sys.stderr)
    return listings
