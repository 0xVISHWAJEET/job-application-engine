"""
One-time onboarding: turn a resume/CV (PDF, .txt, .md, or .tex) into
profile/candidate_profile.json - the structured source of truth every other
script in this repo (match_score.py, tailor_cv.py, cover_letter.py,
generate_qa.py, discover_jobs.py) reads from. Extraction is grounded only in
what the resume actually says - nothing is invented, and any field the
resume doesn't cover is left null/empty for you to fill in by hand.

This is the step that makes the repo usable by anyone: clone, run this
against your own resume, then run discover_jobs.py.

Usage:
    export GOOGLE_API_KEY=...
    python3 scripts/setup_profile.py path/to/your_resume.pdf
    python3 scripts/setup_profile.py path/to/your_resume.tex
    python3 scripts/setup_profile.py path/to/your_resume.txt

Writes profile/candidate_profile.json (gitignored - never committed, stays
local). Re-run any time your resume changes; it overwrites the existing
file, so copy it aside first if you've hand-edited preferences you want to
keep.
"""
import json
import sys
from pathlib import Path

from gemini_client import GeminiError, generate
import render_base_resume

ROOT = Path(__file__).parent.parent
PROFILE_PATH = ROOT / "profile" / "candidate_profile.json"

SCHEMA_INSTRUCTIONS = """Extract this resume into EXACTLY this JSON schema. Use null for any
field the resume doesn't state - never invent a value, metric, employer, date, or credential
that isn't in the text below.

{
  "profile": {
    "first_name": string, "last_name": string, "email": string or null,
    "phone": string or null, "location": string or null,
    "open_to_remote": true,
    "linkedin": string or null, "github": string or null,
    "headline": "a short, specific professional headline derived from the resume's actual roles/skills - not a generic title",
    "years_experience_total": number (your best estimate from the earliest start_date to now)
  },
  "preferences": {
    "target_roles": ["3-5 role titles this resume's experience actually qualifies the candidate for - infer from their most recent/senior positions, don't guess unrelated roles"],
    "job_types": ["Full-Time", "Contract", "Remote"],
    "min_match_score": 0.75,
    "target_platforms": ["LinkedIn", "Direct company career pages"]
  },
  "vault_memory_seed": {
    "work_authorization": "best-effort inference from location/nationality cues in the resume, or null if none",
    "requires_sponsorship": null,
    "willing_to_relocate": null,
    "notice_period_days": null
  },
  "skills": {
    "<pick 3-6 category names that actually fit this candidate's background, e.g. 'languages', 'cloud_infrastructure', 'frontend', 'data' - whatever groups their real skills sensibly>": ["skill", "skill", "..."]
  },
  "experience": [
    {"company": string, "position": string, "start_date": "YYYY-MM" or null, "end_date": "YYYY-MM" or \"present\" or null,
     "location": string or null, "highlights": ["each real bullet/achievement from the resume, verbatim or lightly cleaned up - never embellished"]}
  ],
  "education": [
    {"institution": string, "degree": string, "start_date": "YYYY-MM" or null, "end_date": "YYYY-MM" or null, "details": string or null}
  ],
  "summary_template": "a 3-5 sentence professional summary grounded only in the experience/skills above, written in third person, no fabricated metrics"
}

Return ONLY the JSON object - no markdown fences, no commentary.

Resume text:
"""


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(errors="replace")


def build_profile(resume_text: str) -> dict:
    prompt = SCHEMA_INSTRUCTIONS + resume_text
    raw = generate(prompt).strip()
    # Gemini sometimes wraps JSON in ```json fences despite instructions not to.
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        raw = raw[4:] if raw.startswith("json") else raw
    return json.loads(raw.strip())


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} path/to/your_resume.(pdf|txt|md|tex)", file=sys.stderr)
        sys.exit(1)

    resume_path = Path(sys.argv[1])
    if not resume_path.exists():
        print(f"No such file: {resume_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {resume_path}...")
    resume_text = _extract_text(resume_path)
    if not resume_text.strip():
        print("Could not extract any text from that file - is it a scanned/image-only PDF?", file=sys.stderr)
        sys.exit(1)

    print("Extracting structured profile (one Gemini call)...")
    try:
        profile = build_profile(resume_text)
    except GeminiError as exc:
        print(f"Profile extraction failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"Model returned non-JSON output, try again: {exc}", file=sys.stderr)
        sys.exit(1)

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2) + "\n")

    print(f"\nWrote {PROFILE_PATH}")
    print(f"Target roles inferred: {', '.join(profile.get('preferences', {}).get('target_roles', []))}")

    print("\nRendering base_resume.tex from your profile...")
    try:
        render_base_resume.main()
    except Exception as exc:
        print(f"(base resume render/compile skipped: {exc})", file=sys.stderr)

    print(
        "\nReview profile/candidate_profile.json for accuracy, then tune "
        "preferences.target_roles / min_match_score to taste - re-run "
        "`python3 scripts/render_base_resume.py` after any edit so "
        "profile/base_resume.tex picks them up. If you're using the career-ops "
        "reverse-ATS scan (see README), copy "
        "vendor/career-ops/templates/portals.example.yml to "
        "vendor/career-ops/portals.yml and set title_filter.positive to the "
        "same target roles.\n\nThen run: python3 scripts/discover_jobs.py"
    )


if __name__ == "__main__":
    main()
