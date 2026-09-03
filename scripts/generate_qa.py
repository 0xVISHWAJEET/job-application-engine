"""
Generates likely screening-question answers for a specific job, grounded
only in the candidate's actual resume/experience/projects - checks the
vault for an exact answer first (reused as-is), and for anything not
already saved, drafts a grounded answer and marks it "generated" so it's
clear that one deserves a read before use. Nothing here is fabricated:
the prompt is instructed to answer only from the given profile data, or
say so plainly if it can't.

Usage:
    python3 generate_qa.py "path/to/jd.txt"                    # print only
    python3 generate_qa.py "path/to/jd.txt" --job-id 3          # also save to DB + write .md
"""

import json
import sys
from pathlib import Path

from gemini_client import GeminiError, generate

sys.path.insert(0, str(Path(__file__).parent.parent / "jobs"))
sys.path.insert(0, str(Path(__file__).parent.parent / "vault"))

from jobs_db import JobsDB  # noqa: E402
from vault import Vault  # noqa: E402

PROFILE_PATH = Path(__file__).parent.parent / "profile" / "candidate_profile.json"
OUTPUT_DIR = Path(__file__).parent.parent / "jobs" / "outputs"


def _ask_gemini_for_questions(job_description: str, profile: dict, already_known: dict[str, str]) -> list[dict]:
    prompt = f"""You are predicting the screening/application questions a candidate is
likely to be asked for this job posting, and drafting answers grounded ONLY in
the candidate data given below - never invent an achievement, employer, metric,
or skill not already present. If the profile genuinely doesn't support a good
answer to a question you'd otherwise predict, skip that question rather than
guessing.

Candidate profile:
{json.dumps(profile, indent=2)}

Answers already on file from previous applications (reuse verbatim if a
predicted question matches one of these, don't redraft it):
{json.dumps(already_known, indent=2)}

Job description:
{job_description}

Return ONLY a JSON array (no markdown fences, no other text) of 5-10 objects,
each with exactly these keys:
- "question": the likely screening question, phrased as a real application
  form would ask it
- "answer": a grounded answer from the candidate data above (or, if it
  exactly matches one of the "already known" answers, that exact text)
- "already_known": true if this reuses an "already known" answer verbatim, else false
"""

    raw = generate(prompt).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())


def generate_qa_for_job(job_description: str) -> list[dict]:
    profile = json.loads(PROFILE_PATH.read_text())
    vault = Vault()
    already_known = vault.all()

    predicted = _ask_gemini_for_questions(job_description, profile, already_known)

    qa_pairs = []
    for item in predicted:
        source = "vault" if item.get("already_known") else "generated"
        qa_pairs.append({"question": item["question"], "answer": item["answer"], "source": source})

    return qa_pairs


def write_qa_markdown(company: str, role: str, qa_pairs: list[dict]) -> Path:
    from tailor_cv import _slugify

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"tailored_{_slugify(company)}_{_slugify(role)}_QA.md"

    lines = [f"# Likely screening questions - {role} @ {company}", ""]
    for qa in qa_pairs:
        tag = "(from vault - reused)" if qa["source"] == "vault" else "(drafted - review before using)"
        lines.append(f"**Q: {qa['question']}** {tag}")
        lines.append(f"A: {qa['answer']}")
        lines.append("")

    path.write_text("\n".join(lines))
    return path


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <jd_file_path> [--job-id N]", file=sys.stderr)
        sys.exit(1)

    job_description = Path(sys.argv[1]).read_text()

    try:
        qa_pairs = generate_qa_for_job(job_description)
    except GeminiError as exc:
        print(f"Q&A generation failed: {exc}", file=sys.stderr)
        sys.exit(1)

    for qa in qa_pairs:
        tag = "[vault]" if qa["source"] == "vault" else "[generated - review]"
        print(f"{tag} Q: {qa['question']}")
        print(f"         A: {qa['answer']}\n")

    if "--job-id" in sys.argv:
        job_id = int(sys.argv[sys.argv.index("--job-id") + 1])
        db = JobsDB()
        db.replace_questions(job_id, qa_pairs)
        print(f"Saved {len(qa_pairs)} Q&A pairs for job_id={job_id}")


if __name__ == "__main__":
    main()
