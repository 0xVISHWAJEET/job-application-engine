# Job Application Engine

A tested, end-to-end pipeline for job searching and applying, built around
`/home/aspirez/2026/vishwajeet.tex` as the base resume. Covers everything
from `job automate.md`'s spec **except** the parts that mean defeating
platform anti-automation defenses or submitting applications with no human
review - see "What this deliberately does not do" below.

## What's here

```
job-application-engine/
├── resume/compile.sh              # compiles any .tex to PDF via TinyTeX (tested, works)
├── profile/candidate_profile.json # structured source of truth: contact info, every
│                                   # experience bullet, skills, education - extracted
│                                   # from vishwajeet.tex, nothing fabricated
├── vault/
│   ├── vault.py                   # SQLite Q&A store for recurring screening questions
│   └── answers.db                 # seeded with 9 answers from candidate_profile.json
├── scripts/
│   ├── gemini_client.py           # dependency-free (stdlib urllib) Gemini REST client
│   ├── match_score.py             # scores a JD against the profile, 0.0-1.0
│   ├── tailor_cv.py               # tailors summary + experience bullets to a JD,
│   │                               # renders back into vishwajeet.tex's own LaTeX
│   │                               # macros, compiles to PDF - TESTED END TO END
│   ├── mcp_server.py               # exposes score_job/tailor_cv/vault_get/vault_set/
│   │                               # vault_list/get_candidate_profile as MCP tools -
│   │                               # TESTED via the real call_tool() interface
│   ├── discover_jobs.py           # discovers listings across every source in
│   │                               # "Portal coverage" below, scores + tailors + generates
│   │                               # Q&A for every one that clears MIN_SCORE
│   ├── ats_boards.py              # generic Greenhouse/Lever/Ashby discoverers, used by
│   │                               # discover_jobs.py for the AI/blockchain company boards
│   ├── generate_qa.py             # predicts screening questions for a JD and drafts
│   │                               # grounded answers from candidate_profile.json/vault
│   └── backfill_tailor.py         # one-off: tailors + generates Q&A for jobs already in
│                                   # jobs.db that are missing either
└── jobs/
    ├── jobs_db.py                  # SQLite schema/access (jobs, job_questions tables)
    ├── jobs.db                     # every discovered listing, its score, and (for
    │                               # qualifying ones) its tailored PDF path
    └── outputs/                    # tailored_<Company>_<Role>.pdf + _QA.md per qualifying job
```

## Portal coverage

`URL.txt` lists 196 job-portal URLs. Each was checked for a way to read
real listings without logging in and without defeating any anti-bot
measure (see "What this deliberately does not do") - global by default,
not filtered by country/region, since the candidate is open to relocating
(remote preferred). Working sources, wired into `discover_jobs.py`:

| Source | How | Notes |
|---|---|---|
| RemoteOK | public JSON API | `remoteok.com/api` |
| WeWorkRemotely | public per-category RSS | 2 categories |
| web3.career | server-rendered HTML table | no login wall |
| Dice | server-rendered search results | JSON-LD `JobPosting` on each detail page gives exact `datePosted` + full description |
| Remotive | public JSON API | rate-respecting: a couple of calls per run, always links back to remotive.com, per their published terms |
| Wellfound | server-rendered `/jobs` feed | |
| BuiltIn | server-rendered category pages, 4 domains | `builtin.com` + its Boston/Chicago/Austin sister sites (from URL.txt) - confirmed to share identical markup |
| GitJobs | server-rendered job cards with `data-job-*` attributes | CNCF/Linux Foundation's open-source board; `jobs.cncf.io` and `jobs.linuxfoundation.org` both redirect here - an earlier pass wrongly assumed this was JS-only, corrected after a direct recheck |
| JustJoinIT | server-rendered category pages | major Polish/European tech board; `devops`/`ai`/`security`/`go` categories |
| LinkedIn | public/guest job-search page | 16 distinct keyword searches (DevOps/SRE/Blockchain/AI/Cryptography variants) - each returns up to ~60 results; pagination past that (`start=25+`) redirects to `start=0` without a login, confirmed via the 303 response, so more keywords is the only way to get more without crossing into logged-in automation |
| 31 company boards | Greenhouse/Lever/Ashby public APIs | Anthropic, OpenAI, Cohere, Scale AI, Stability AI, DeepMind, Together AI, Mistral, Coinbase, Consensys, NEAR Foundation, Kraken, Circle, Solana Labs, Cloudflare, Stripe, Databricks, GitLab, Snowflake, Elastic, MongoDB, PagerDuty, New Relic, Datadog, Vercel, Alchemy, Confluent, xAI, ElevenLabs, Replit, Render - these are the actual ATS vendors behind most companies' JS-rendered `/careers` pages, found by direct probing (`boards-api.greenhouse.io`, `api.lever.co`, `api.ashbyhq.com`), not by scraping the page itself |

That's ~40 real sources total, spanning every listed AI/blockchain
company's actual career-page backend plus every general-purpose board that
turned out to be reachable - not scoped to any one country.

**Checked and excluded, with the specific reason** (so this doesn't get
silently re-attempted):
- **Active Cloudflare bot-challenge, even with a real browser**
  (`browser_navigate` returns "Just a moment..." / HTTP 403): himalayas.app,
  cryptojobslist.com. Getting past this specific kind of check is the
  anti-bot-evasion line this project holds regardless of what tooling is
  available - see "What this deliberately does not do".
- **JS-rendered SPA, no real listings via plain HTTP or a real browser**:
  arc.dev (its own inventory is a single listing plus a WeWorkRemotely
  referral banner - not worth a dedicated scraper), nodesk.co,
  justremote.co, cryptocurrencyjobs.co (homepage and category pages are
  both nav-only), laborx.com (loads its actual postings client-side; also
  turned out to be a *freelance* gig marketplace, not full-time roles, once
  inspected with a real browser), jobgether.com, getonbrd.com.
- **Not a listing page at all**: jobs.solana.com (triggers a file download
  instead of rendering), careers.near.org (timed out; already covered via
  the `nearfoundation` Greenhouse board instead), Indeed, Naukri (empty
  JS shell / blocks non-browser requests).
- **The remaining ~150 URLs**: batch-probed for reachability and, for the
  108 that responded, scanned for real job-listing signals (role-keyword
  hits in link text, presence of a search box) rather than assumed - the
  large majority came back with 0 role-keyword hits even where reachable
  (generic country job boards - European, Gulf, East/Southeast Asian, Latin
  American, African - with no realistic DevOps/SRE/Blockchain/AI/
  Cryptography volume). A handful scored well (jobgether.com, getonbrd.com)
  but turned out to be JS-rendered per the point above.

A real browser (Playwright MCP tools) **is** available and working in this
environment - confirmed after the user installed its system dependencies
(`sudo npx playwright install-deps`) outside this session. It unlocked
GitJobs's true structure (leading to the correction above) but doesn't help
with sites behind an active bot-challenge, which stays a deliberate
boundary rather than a technical one.

Everything above is built and verified working - `tailor_cv.py` was run
against a real job description and produced a correctly re-emphasized,
non-fabricated, properly-formatted PDF (see git history / just run it
again to confirm).

## Usage

```bash
export GOOGLE_API_KEY=$(grep GOOGLE_API_KEY ../VishuGPT/.env | cut -d= -f2)

# 0. Run the full pipeline: discover across every source in "Portal coverage"
#    above, score each against candidate_profile.json, and tailor a resume +
#    generate Q&A for every one that scores >= MIN_SCORE (0.80) and was
#    posted within the last 30 days. Populates jobs/jobs.db and jobs/outputs/.
python3 scripts/discover_jobs.py

# 1. Or score a single posting before spending effort on it
python3 scripts/match_score.py path/to/jd.txt

# 2. If it clears your threshold (0.75, set in candidate_profile.json),
#    tailor a resume for it
python3 scripts/tailor_cv.py "Company Name" "Role Title" path/to/jd.txt
# -> jobs/outputs/tailored_Company_Name_Role_Title.pdf

# 3. Recompile the base resume any time vishwajeet.tex changes
resume/compile.sh
```

### As an MCP server

The same operations are also exposed over MCP, so any MCP client (Claude
Code, Claude Desktop, or VishuGPT via its own `mcp_client.py`) can call
`score_job`, `tailor_cv`, `vault_get`, `vault_set`, `vault_list`, and
`get_candidate_profile` directly:

```bash
python3 scripts/mcp_server.py                # stdio - add to Claude Desktop/Code's MCP config
python3 scripts/mcp_server.py --http 8090     # Streamable HTTP - point VishuGPT's
                                               # MCP_SERVERS env var at http://host:8090/mcp
```

**Proofread every tailored PDF before sending it.** The LLM only reorders/
trims/lightly rewords bullets that already exist in `candidate_profile.json`
- it's instructed not to invent anything - but light rewording can still
introduce a small grammar slip (e.g. a verb tense) worth a 30-second read
before it goes out.

## Applying to a specific posting (the part that stays human-driven)

Give me (Claude) the job posting URL directly in chat, in this project or
VishuGPT, and I can:

1. Fetch the posting and read it (plain HTTP - real browser automation via
   the Playwright MCP tools is present but **not actually usable in this
   environment**: `browser_navigate` needs OS-level dependencies installed
   via `sudo npx playwright install-deps`, which needs root, which this
   host doesn't grant non-interactively - confirmed, not assumed)
2. Run `match_score.py` / `tailor_cv.py` for that specific role
3. Walk you through the application form fields using
   `candidate_profile.json` and `vault/answers.db` for the answers, and
   `generate_qa.py`'s predictions for likely screening questions
4. For any screening question the vault doesn't already have an answer
   for, ask you directly rather than guessing, then save your answer to
   the vault so the same question doesn't need asking next time
5. You do the actual clicking/typing/submitting yourself, since I can't
   drive a real browser here

This isn't a background/scheduled job - it happens live, per posting, in
conversation with you.

## What this deliberately does not do

`job automate.md`'s spec calls for a few things I'm not building, because
they're not implementation details - they're the actual purpose of those
specific pieces:

- **`invisible_playwright`** (or any browser patched to strip automation
  flags / pass Cloudflare Turnstile, reCAPTCHA, hCaptcha) - a tool whose
  job is defeating the anti-bot defenses a platform deploys on purpose.
- **Automated account creation via disposable/aliased emails** to route
  around a platform's normal signup/verification flow.
- **Bypassing MFA or other security gates.**
- **Fully autonomous final-submit as the default** (the spec makes human
  approval an optional config flag, not a requirement) - every
  application here gets submitted by you, every time.

Doing any of these means building something whose main function is
circumventing measures LinkedIn/Naukri/Wellfound/etc. put there
specifically to stop this - true regardless of intent, and it also risks
your own accounts getting banned for exactly the bot-like behavior those
systems are built to detect. Everything else in the spec - discovery,
scoring, tailoring, persistent memory, semi-automated filling with a human
final click - is built above and works.
