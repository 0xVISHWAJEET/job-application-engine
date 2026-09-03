"""
Persistent answers vault for recurring job-application screening questions
("years of experience with X?", "willing to relocate?", "expected salary?").
Exact-match lookups (question -> answer) in SQLite; nothing here fills in
or submits anything on its own - it's read/written by whoever is filling a
form (you, or Claude assisting live via browser tools) so the same question
doesn't need answering from scratch on every application.

Usage:
    from vault import Vault
    v = Vault()
    v.get("years of experience with kubernetes")   # -> "4+" or None
    v.set("years of experience with kubernetes", "4+")
    v.all()                                          # -> {question: answer, ...}
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "answers.db"


class Vault:
    def __init__(self, db_path: Path = DB_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS answers (
                question_key TEXT PRIMARY KEY,
                answer TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    @staticmethod
    def _normalize(question: str) -> str:
        return " ".join(question.strip().lower().split())

    def get(self, question: str) -> str | None:
        row = self.conn.execute(
            "SELECT answer FROM answers WHERE question_key = ?", (self._normalize(question),)
        ).fetchone()
        return row[0] if row else None

    def set(self, question: str, answer: str) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO answers (question_key, answer, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(question_key) DO UPDATE SET
                    answer = excluded.answer, updated_at = excluded.updated_at
                """,
                (self._normalize(question), answer),
            )

    def all(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT question_key, answer FROM answers").fetchall()
        return dict(rows)


def seed_from_profile(profile_path: Path) -> None:
    """One-time seed: loads candidate_profile.json's vault_memory_seed into the vault."""
    import json

    with open(profile_path) as f:
        profile = json.load(f)

    vault = Vault()
    for key, value in profile.get("vault_memory_seed", {}).items():
        if value is not None:
            vault.set(key.replace("_", " "), str(value))

    print(f"Seeded {len(profile.get('vault_memory_seed', {}))} answers into {DB_PATH}")


if __name__ == "__main__":
    seed_from_profile(Path(__file__).parent.parent / "profile" / "candidate_profile.json")
