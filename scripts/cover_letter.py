"""
Drafts a cover letter for a specific job posting, grounded only in
candidate_profile.json's real experience/skills - never inventing a new
achievement, metric, employer, or skill that isn't already present there.
Writes to jobs/outputs/ as Markdown. Draft only - never sends or submits
anything. Pair with tailor_cv.py's resume for the same posting.

Usage:
    python3 cover_letter.py "Company Name" "Role Title" path/to/jd.txt
Produces:
    ../jobs/outputs/cover_letter_Company_Name_Role_Title.md

As a library (used by discover_jobs.py):
    from cover_letter import write_cover_letter
    path = write_cover_letter(company, role, job_description)
"""
import json
import re
import sys
from pathlib import Path

from gemini_client import GeminiError, generate

ROOT = Path(__file__).parent.parent
PROFILE_PATH = ROOT / "profile" / "candidate_profile.json"
OUTPUT_DIR = ROOT / "jobs" / "outputs"


def _slugify(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")


def generate_cover_letter(company: str, role: str, job_description: str, profile: dict) -> str:
    prompt = f"""You may ONLY use facts present in the candidate profile below - never invent
a new achievement, metric, employer, skill, or credential that isn't already present. In
particular, never imply a scope of responsibility - e.g. formal people management, direct
reports, mentoring a team - unless an experience highlight explicitly says so. If the JD
calls for something the candidate's profile doesn't support, address the gap honestly
(frame genuinely transferable experience) rather than claiming experience that isn't there.

Write a cover letter for this candidate applying to the role below. From:
{profile['profile']['first_name']} {profile['profile']['last_name']}
({profile['profile']['email']}, {profile['profile']['phone']}, {profile['profile']['location']}).

Keep it under 300 words, 3-4 short paragraphs: an opening naming the role and company,
2-3 concrete proof points drawn from the experience/skills below most relevant to this JD,
one line on why this company specifically, and a closing call to action. Professional but
not stiff. Do not use markdown formatting (no **bold**, no [links]) - plain text only,
since this may be pasted directly into an application form or email body.

Candidate's full experience inventory (source of truth):
{json.dumps(profile["experience"], indent=2)}

Candidate's skills:
{json.dumps(profile["skills"], indent=2)}

Company: {company}
Role: {role}

Job description:
{job_description}

Return ONLY the cover letter text, starting with "Dear Hiring Team," and ending with
the candidate's name - no subject line, no markdown fences, no other commentary.
"""
    return generate(prompt)


def write_cover_letter(company: str, role: str, job_description: str, profile: dict | None = None) -> Path:
    """Generates and writes a cover letter for (company, role, job_description),
    loading candidate_profile.json itself if `profile` isn't passed. Returns
    the written file's path. Raises GeminiError on generation failure."""
    if profile is None:
        profile = json.loads(PROFILE_PATH.read_text())

    letter = generate_cover_letter(company, role, job_description, profile)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"cover_letter_{_slugify(company)}_{_slugify(role)}.md"
    out_path.write_text(letter.strip() + "\n")
    return out_path


def main():
    if len(sys.argv) != 4:
        print(f"Usage: python3 {sys.argv[0]} <company> <role> <jd_file_path>", file=sys.stderr)
        sys.exit(1)

    company, role, jd_path = sys.argv[1], sys.argv[2], sys.argv[3]
    job_description = Path(jd_path).read_text()

    try:
        out_path = write_cover_letter(company, role, job_description)
    except GeminiError as exc:
        print(f"Cover letter drafting failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {out_path} (draft only - not sent/submitted)")


if __name__ == "__main__":
    main()
