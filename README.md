# job-search

A complete, self-hosted job-search pipeline: give it your resume, and it
discovers openings across ~180 real sources worldwide, scores each one
against your actual background, and - for anything that clears your
threshold - tailors a resume, drafts a cover letter, and predicts likely
screening questions with grounded answers. Everything runs on your own
machine against your own data; nothing is invented, and nothing gets
submitted anywhere without you.

No account signup, no paid API beyond a free-tier Gemini key, and no
bot-detection bypass anywhere - see
["What this deliberately does not do"](#what-this-deliberately-does-not-do).

## Quickstart

```bash
git clone https://github.com/0xVISHWAJEET/job-search.git
cd job-search

# 1. Python deps (a venv keeps this isolated from system Python)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Node (for career-ops's reverse-ATS scan) and Bun (for freehire-search) -
#    skip either if you don't want that source; discover_jobs.py degrades
#    gracefully if a vendored tool is missing
./scripts/setup_career_ops.sh
curl -fsSL https://bun.sh/install | bash   # only if you don't already have bun

# 3. A free Gemini API key (https://aistudio.google.com/apikey) - used for
#    scoring/tailoring/cover-letters/Q&A, nothing else
cp .env.example .env
# edit .env, set GOOGLE_API_KEY=...
export GOOGLE_API_KEY=$(grep GOOGLE_API_KEY .env | cut -d= -f2)

# 4. Share your resume - this is the only personal input the whole
#    pipeline needs. Extracts a structured profile + a compilable base
#    resume from it; nothing is fabricated, anything the resume doesn't
#    state is left blank for you to fill in.
python3 scripts/setup_profile.py path/to/your_resume.pdf
#   -> profile/candidate_profile.json (review this for accuracy)
#   -> profile/base_resume.pdf (needs a LaTeX distro - see below)

# 5. (optional) Tune which roles the career-ops reverse-ATS scan keeps -
#    without this it still runs, just unfiltered by title
cp vendor/career-ops/templates/portals.example.yml vendor/career-ops/portals.yml
# edit title_filter.positive to your target roles

# 6. Run the full pipeline: discover across every source below, score each
#    against your profile, and for anything that qualifies, tailor a
#    resume + cover letter + predicted Q&A
python3 scripts/discover_jobs.py

# 7. Browse results
python3 scripts/webapp.py 8095   # -> http://localhost:8095
```

**LaTeX, for the tailored PDF resumes.** `resume/compile.sh` calls
`pdflatex`. Either `apt install texlive-latex-extra` (or your distro's
equivalent) or install [TinyTeX](https://yihui.org/tinytex/), a lightweight
LaTeX-on-demand installer. Everything else (discovery, scoring, cover
letters, Q&A) works without it - only the compiled PDF step needs it.

## What's here

```
job-search/
├── resume/
│   ├── compile.sh                 # compiles any .tex to PDF via pdflatex
│   └── templates/
│       └── base_resume_template.tex  # generic LaTeX template, rendered by
│                                      # render_base_resume.py into your own
│                                      # profile/base_resume.tex
├── profile/
│   └── candidate_profile.example.json  # schema reference - your own
│                                        # candidate_profile.json/base_resume.*
│                                        # are gitignored, generated locally
├── vault/
│   ├── vault.py                   # SQLite Q&A store for recurring screening questions
│   └── answers.db                 # local, gitignored - seeded from your own profile
├── scripts/
│   ├── setup_profile.py           # resume -> candidate_profile.json + base_resume.tex
│   │                               # (the one command that makes this repo yours)
│   ├── render_base_resume.py      # candidate_profile.json -> base_resume.tex/.pdf
│   ├── gemini_client.py           # dependency-free (stdlib urllib) Gemini REST client
│   ├── match_score.py             # scores a JD against your profile, 0.0-1.0
│   ├── tailor_cv.py               # tailors summary + experience bullets to a JD,
│   │                               # renders back into base_resume.tex's macros,
│   │                               # compiles to PDF
│   ├── cover_letter.py            # drafts a cover letter for a specific posting,
│   │                               # grounded only in your real experience
│   ├── generate_qa.py             # predicts screening questions for a JD and drafts
│   │                               # grounded answers from your profile/vault
│   ├── posting_guard.py           # integrity gate: strips hidden HTML/invisible-
│   │                               # Unicode/instruction-shaped content from a fetched
│   │                               # posting before it reaches any LLM prompt
│   ├── discover_jobs.py           # orchestrates every source below, then
│   │                               # scores/tailors/drafts qualifying jobs
│   ├── ats_boards.py              # ~130 curated companies' Greenhouse/Lever/Ashby boards
│   ├── career_ops_bridge.py       # bridges vendor/career-ops's reverse-ATS
│   │                               # directory scan (see below) into the pipeline
│   ├── freehire_bridge.py         # bridges vendor/ai-job-search's freehire-search
│   │                               # CLI (see below) into the pipeline
│   ├── mcp_server.py              # exposes score_job/tailor_cv/vault_* as MCP tools
│   └── backfill_tailor.py         # one-off: tailors + generates Q&A for jobs already
│                                   # in jobs.db that are missing either
├── vendor/
│   ├── career-ops/                # vendored github.com/career-ops-hq/career-ops -
│   │   └── portals.yml            # your tuned title_filter (gitignored, personal)
│   └── ai-job-search/
│       └── freehire-search/       # vendored skill from github.com/ai-job-search-dev/ai-job-search
└── jobs/
    ├── jobs_db.py                  # SQLite schema/access (jobs, job_questions tables)
    ├── jobs.db                     # local, gitignored - every discovered listing,
    │                               # its score, and (for qualifying ones) its
    │                               # tailored PDF + cover letter paths
    └── outputs/                    # tailored_<Company>_<Role>.pdf/.tex,
                                    # cover_letter_<Company>_<Role>.md, *_QA.md
```

## Portal coverage

Every source here was checked for a way to read real listings without
logging in and without defeating any anti-bot measure - see
["What this deliberately does not do"](#what-this-deliberately-does-not-do).
Global by default, not filtered by country/region.

| Source | How | Notes |
|---|---|---|
| RemoteOK | public JSON API | `remoteok.com/api` |
| WeWorkRemotely | public per-category RSS | 2 categories |
| web3.career | server-rendered HTML table | no login wall |
| Dice | server-rendered search results | JSON-LD `JobPosting` on each detail page gives exact `datePosted` + full description |
| Remotive | public JSON API | rate-respecting |
| Wellfound | server-rendered `/jobs` feed | |
| BuiltIn | server-rendered category pages, 4 domains | `builtin.com` + its Boston/Chicago/Austin sister sites |
| GitJobs | server-rendered job cards | CNCF/Linux Foundation's open-source board |
| JustJoinIT | server-rendered category pages | major Polish/European tech board |
| LinkedIn | public/guest job-search page | keyword-search based, no login |
| ~130 curated company boards | Greenhouse/Lever/Ashby public APIs | `scripts/ats_boards.py` - AI labs, ML infra, dev-tools, security, blockchain/fintech, large general-tech companies |
| **career-ops reverse-ATS scan** | public company-directory walk | Greenhouse/Lever/Ashby/Workday/iCIMS/BambooHR/Paylocity/join.com - ~8,000+ companies per vendor, filtered by `portals.yml`'s `title_filter`. Zero LLM tokens, pure HTTP+JSON. |
| **freehire.me aggregator** | public JSON API | ~50 ATS platforms normalized into one schema across many countries - each result already carries its full description, no follow-up fetch needed |

That's roughly 180 real sources, not scoped to any one country - global
tech company directories plus every general-purpose board that turned out
to be reachable.

## Usage

```bash
export GOOGLE_API_KEY=$(grep GOOGLE_API_KEY .env | cut -d= -f2)

# 0. Run the full pipeline: discover across every source above, score each
#    against your profile, and tailor a resume + cover letter + Q&A for
#    every one that scores >= MIN_SCORE (0.80) and was posted within the
#    last 30 days. Populates jobs/jobs.db and jobs/outputs/.
python3 scripts/discover_jobs.py

# 1. Or score a single posting before spending effort on it
python3 scripts/match_score.py path/to/jd.txt

# 2. If it clears your threshold, tailor a resume for it
python3 scripts/tailor_cv.py "Company Name" "Role Title" path/to/jd.txt
# -> jobs/outputs/tailored_Company_Name_Role_Title.pdf

# 3. Draft a cover letter for the same posting
python3 scripts/cover_letter.py "Company Name" "Role Title" path/to/jd.txt
# -> jobs/outputs/cover_letter_Company_Name_Role_Title.md

# 4. Recompile your base resume any time candidate_profile.json changes
python3 scripts/render_base_resume.py
```

### As an MCP server

The same operations are also exposed over MCP, so any MCP client (Claude
Code, Claude Desktop, or your own agent) can call `score_job`, `tailor_cv`,
`vault_get`, `vault_set`, `vault_list`, and `get_candidate_profile` directly:

```bash
python3 scripts/mcp_server.py                # stdio - add to Claude Desktop/Code's MCP config
python3 scripts/mcp_server.py --http 8090     # Streamable HTTP
```

**Proofread every tailored PDF and cover letter before sending it.** The
LLM only reorders/trims/lightly rewords content that already exists in
your profile - it's instructed not to invent anything - but light
rewording can still introduce a small grammar slip worth a 30-second read
before it goes out.

## Applying to a specific posting (the part that stays human-driven)

Give an AI assistant the job posting URL directly in chat, and it can:

1. Fetch the posting and read it (plain HTTP only - no browser automation
   aimed at defeating anti-bot measures)
2. Run `match_score.py` / `tailor_cv.py` / `cover_letter.py` for that specific role
3. Walk you through the application form fields using
   `candidate_profile.json` and `vault/answers.db` for the answers, and
   `generate_qa.py`'s predictions for likely screening questions
4. For any screening question the vault doesn't already have an answer
   for, ask you directly rather than guessing, then save your answer to
   the vault so the same question doesn't need asking next time
5. You do the actual clicking/typing/submitting yourself

This isn't a background/scheduled job - it happens live, per posting, in
conversation.

## What this deliberately does not do

- **No browser patched to strip automation flags or pass Cloudflare
  Turnstile/reCAPTCHA/hCaptcha** - defeating anti-bot defenses a platform
  deploys on purpose isn't in scope, regardless of what tooling is available.
- **No automated account creation via disposable/aliased emails.**
- **No bypassing MFA or other security gates.**
- **No fully autonomous final-submit.** Every application gets submitted
  by you, every time - this tool drafts and prepares, it never clicks
  "Submit" on its own.

Doing any of these means building something whose main function is
circumventing measures platforms put there specifically to stop this - and
it risks your own accounts getting flagged for exactly the bot-like
behavior those systems are built to detect. Everything else - discovery,
scoring, tailoring, persistent memory, semi-automated filling with a human
final click - is built above and works.

## Credits

- [career-ops](https://github.com/career-ops-hq/career-ops) (MIT) -
  vendored for its reverse-ATS-directory scanner.
- [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) (MIT,
  © Mads Lorentzen) - vendored for `freehire-search` (the freehire.me
  aggregator bridge) and `posting_guard.py` (the prompt-injection scrubber).
