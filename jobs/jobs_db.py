"""
Job discovery database - one row per qualifying posting (match_score >= 0.80,
posted within the last 30 days): portal, role, company, URL to apply at, and
the path to its tailored resume PDF. This is the "extensive list/db" the
discovery pipeline (discover_jobs.py) writes into and match_score.py/
tailor_cv.py feed off of.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    role_category TEXT,          -- DevOps / SRE / Blockchain / AI / Cryptography
    location TEXT,
    apply_url TEXT NOT NULL UNIQUE,
    posted_date TEXT,            -- ISO date, best-effort from the listing
    match_score REAL,
    match_reasoning TEXT,
    tailored_resume_path TEXT,
    cover_letter_path TEXT,
    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'discovered'   -- discovered / scored / tailored / skipped_low_score / applied
);

CREATE TABLE IF NOT EXISTS job_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source TEXT NOT NULL   -- 'vault' (exact reuse of a saved answer) or
                            -- 'generated' (drafted from resume/profile - review before using)
)
"""


class JobsDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        # Migration for jobs.db files created before cover_letter_path existed -
        # CREATE TABLE IF NOT EXISTS above doesn't add columns to an existing table.
        try:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN cover_letter_path TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    def add_or_update(self, **fields) -> int:
        """Insert a job, or update it in place if apply_url already exists (re-running discovery is idempotent)."""
        existing = self.conn.execute(
            "SELECT id FROM jobs WHERE apply_url = ?", (fields["apply_url"],)
        ).fetchone()

        if existing:
            job_id = existing[0]
            set_clause = ", ".join(f"{k} = ?" for k in fields if k != "apply_url")
            values = [v for k, v in fields.items() if k != "apply_url"] + [job_id]
            with self.conn:
                self.conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
            return job_id

        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        with self.conn:
            cursor = self.conn.execute(
                f"INSERT INTO jobs ({columns}) VALUES ({placeholders})", list(fields.values())
            )
        return cursor.lastrowid

    def qualifying(self, min_score: float = 0.80, max_age_days: int = 30) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).date().isoformat()
        rows = self.conn.execute(
            """
            SELECT * FROM jobs
            WHERE match_score >= ? AND (posted_date IS NULL OR posted_date >= ?)
            ORDER BY match_score DESC
            """,
            (min_score, cutoff),
        ).fetchall()
        return rows

    def all(self) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute("SELECT * FROM jobs ORDER BY discovered_at DESC").fetchall()

    def get_by_apply_url(self, apply_url: str) -> sqlite3.Row | None:
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute("SELECT * FROM jobs WHERE apply_url = ?", (apply_url,)).fetchone()

    def replace_questions(self, job_id: int, qa_pairs: list[dict]) -> None:
        """qa_pairs: [{"question": ..., "answer": ..., "source": "vault"|"generated"}, ...]"""
        with self.conn:
            self.conn.execute("DELETE FROM job_questions WHERE job_id = ?", (job_id,))
            self.conn.executemany(
                "INSERT INTO job_questions (job_id, question, answer, source) VALUES (?, ?, ?, ?)",
                [(job_id, qa["question"], qa["answer"], qa["source"]) for qa in qa_pairs],
            )

    def get_questions(self, job_id: int) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute(
            "SELECT * FROM job_questions WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()

    def summary(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        qualifying = self.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE match_score >= 0.80"
        ).fetchone()[0]
        by_portal = self.conn.execute(
            "SELECT portal, COUNT(*) FROM jobs GROUP BY portal"
        ).fetchall()
        return {"total": total, "qualifying_80pct": qualifying, "by_portal": dict(by_portal)}


if __name__ == "__main__":
    db = JobsDB()
    print(f"Database at {DB_PATH}")
    print(db.summary())
