"""
Scores a job description against the candidate profile - a fit signal to
decide whether a posting is worth the time to tailor a resume and apply
for, not an autonomous filter that applies or discards anything on its own.

Usage:
    python3 match_score.py "path/to/jd.txt"
    echo "job description text..." | python3 match_score.py
"""

import json
import sys
from pathlib import Path

from gemini_client import GeminiError, generate

PROFILE_PATH = Path(__file__).parent.parent / "profile" / "candidate_profile.json"


def score(job_description: str, profile: dict) -> dict:
    prompt = f"""You are scoring how well a candidate fits a job posting.

Candidate profile (skills, experience, target roles):
{json.dumps({"skills": profile["skills"], "experience": [
    {"company": e["company"], "position": e["position"], "highlights": e["highlights"]}
    for e in profile["experience"]
], "target_roles": profile["preferences"]["target_roles"]}, indent=2)}

Job description:
{job_description}

Return ONLY a JSON object (no markdown fences, no other text) with exactly these keys:
- "score": a float 0.0-1.0 for overall fit
- "reasoning": one sentence explaining the score
- "matching_skills": array of the candidate's skills/experience that directly match this JD
- "gaps": array of requirements the candidate doesn't clearly meet
"""

    raw = generate(prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())


def main():
    if len(sys.argv) > 1:
        job_description = Path(sys.argv[1]).read_text()
    else:
        job_description = sys.stdin.read()

    if not job_description.strip():
        print("No job description provided.", file=sys.stderr)
        sys.exit(1)

    profile = json.loads(PROFILE_PATH.read_text())

    try:
        result = score(job_description, profile)
    except GeminiError as exc:
        print(f"Scoring failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))

    threshold = profile["preferences"]["min_match_score"]
    if result["score"] >= threshold:
        print(f"\n✓ Above threshold ({threshold}) - worth tailoring a resume for.", file=sys.stderr)
    else:
        print(f"\n✗ Below threshold ({threshold}).", file=sys.stderr)


if __name__ == "__main__":
    main()
