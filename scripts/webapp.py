"""
Local dashboard for jobs.db - browse every qualifying job (score >= 0.80,
posted within the last 30 days) in one page: portal, company, role, match
score/reasoning, a link to the tailored resume PDF, the apply URL, and the
predicted Q&A for that posting. Meant to be the one place you look at while
actually applying, not something published or shared - it's served on
localhost only and reads local files (tailored PDFs) directly off disk.

Usage:
    python3 scripts/webapp.py [port]   # default port 8095
    -> open http://localhost:8095 in a browser
"""

import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent / "jobs"))
from jobs_db import JobsDB  # noqa: E402

DEFAULT_PORT = 8095
MIN_SCORE = 0.80

STYLE = """
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, system-ui, sans-serif; margin: 0; padding: 24px;
         background: #0b0d10; color: #e6e6e6; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #9aa0a6; margin-bottom: 20px; font-size: 13px; }
  .filters { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .filters input, .filters select { background: #1a1d21; border: 1px solid #333; color: #e6e6e6;
         padding: 6px 10px; border-radius: 6px; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #232629; vertical-align: top; }
  th { color: #9aa0a6; font-weight: 600; position: sticky; top: 0; background: #0b0d10; cursor: pointer; }
  tr:hover { background: #14171a; }
  a { color: #7cb8ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .score { font-weight: 700; }
  .score.high { color: #5fd97a; }
  .score.mid { color: #e6c15a; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px;
           background: #232629; color: #c8c8c8; margin-right: 4px; }
  .status-applied { color: #5fd97a; }
  .status-tailored { color: #9aa0a6; }
  .card { background: #14171a; border: 1px solid #232629; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
  .qa { margin-top: 8px; }
  .qa dt { font-weight: 600; margin-top: 12px; }
  .qa dd { margin: 4px 0 0; color: #c8c8c8; }
  .src { font-size: 11px; color: #9aa0a6; margin-left: 6px; }
  .btn { display: inline-block; padding: 8px 14px; border-radius: 6px; margin-right: 8px;
         background: #2563eb; color: white; font-size: 13px; }
  .btn.secondary { background: #232629; color: #e6e6e6; }
  .btn.applied { background: #16a34a; }
  .backlink { display: inline-block; margin-bottom: 16px; }
</style>
"""


def _score_class(score: float) -> str:
    if score >= 0.9:
        return "high"
    if score >= 0.8:
        return "mid"
    return ""


def _page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(title)}</title>{STYLE}</head><body>{body}</body></html>""".encode()


def render_index(db: JobsDB) -> bytes:
    jobs = db.qualifying(min_score=MIN_SCORE, max_age_days=36500)  # dashboard shows all qualifying, age filter already applied at discovery time
    rows = []
    for j in jobs:
        score_cls = _score_class(j["match_score"])
        status_cls = f"status-{j['status']}" if j["status"] else ""
        rows.append(f"""
        <tr data-portal="{html.escape(j['portal'] or '')}" data-role="{html.escape(j['role_category'] or '')}">
          <td class="score {score_cls}">{j['match_score']:.2f}</td>
          <td><a href="/job/{j['id']}">{html.escape(j['title'])}</a></td>
          <td>{html.escape(j['company'] or '')}</td>
          <td><span class="badge">{html.escape(j['portal'] or '')}</span></td>
          <td><span class="badge">{html.escape(j['role_category'] or '')}</span></td>
          <td>{html.escape(j['location'] or '')}</td>
          <td>{html.escape(j['posted_date'] or '')}</td>
          <td class="{status_cls}">{html.escape(j['status'] or '')}</td>
        </tr>""")

    portals = sorted({j["portal"] for j in jobs if j["portal"]})
    roles = sorted({j["role_category"] for j in jobs if j["role_category"]})
    portal_opts = "".join(f'<option value="{html.escape(p)}">{html.escape(p)}</option>' for p in portals)
    role_opts = "".join(f'<option value="{html.escape(r)}">{html.escape(r)}</option>' for r in roles)

    body = f"""
    <h1>Job Application Dashboard</h1>
    <div class="sub">{len(jobs)} qualifying jobs (score &ge; {MIN_SCORE:.2f}). Click a title for the full match
      reasoning, tailored resume, and predicted Q&amp;A.</div>
    <div class="filters">
      <input id="q" placeholder="Search title/company..." oninput="filterRows()">
      <select id="portalFilter" onchange="filterRows()"><option value="">All portals</option>{portal_opts}</select>
      <select id="roleFilter" onchange="filterRows()"><option value="">All roles</option>{role_opts}</select>
    </div>
    <table id="jobsTable">
      <thead><tr>
        <th onclick="sortBy(0)">Score</th><th onclick="sortBy(1)">Title</th><th onclick="sortBy(2)">Company</th>
        <th>Portal</th><th>Role</th><th>Location</th><th onclick="sortBy(6)">Posted</th><th>Status</th>
      </tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
    <script>
      function filterRows() {{
        const q = document.getElementById('q').value.toLowerCase();
        const portal = document.getElementById('portalFilter').value;
        const role = document.getElementById('roleFilter').value;
        document.querySelectorAll('#jobsTable tbody tr').forEach(tr => {{
          const text = tr.innerText.toLowerCase();
          const matchesQ = !q || text.includes(q);
          const matchesPortal = !portal || tr.dataset.portal === portal;
          const matchesRole = !role || tr.dataset.role === role;
          tr.style.display = (matchesQ && matchesPortal && matchesRole) ? '' : 'none';
        }});
      }}
      let sortDir = {{}};
      function sortBy(col) {{
        const tbody = document.querySelector('#jobsTable tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        sortDir[col] = !sortDir[col];
        rows.sort((a, b) => {{
          const av = a.children[col].innerText, bv = b.children[col].innerText;
          const cmp = isNaN(av) ? av.localeCompare(bv) : (parseFloat(av) - parseFloat(bv));
          return sortDir[col] ? cmp : -cmp;
        }});
        rows.forEach(r => tbody.appendChild(r));
      }}
    </script>
    """
    return _page("Job Application Dashboard", body)


def render_job(db: JobsDB, job_id: int) -> bytes | None:
    db.conn.row_factory = None
    row = db.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    cols = [d[0] for d in db.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).description]
    job = dict(zip(cols, row))
    qa_pairs = db.get_questions(job_id)

    resume_link = ""
    if job["tailored_resume_path"] and Path(job["tailored_resume_path"]).exists():
        resume_link = f'<a class="btn secondary" href="/resume/{job_id}" target="_blank">Open tailored resume (PDF)</a>'

    applied = job["status"] == "applied"
    apply_btn_label = "Marked applied" if applied else "Mark as applied"
    apply_btn_cls = "btn applied" if applied else "btn secondary"

    qa_html = ""
    if qa_pairs:
        items = "".join(
            f'<dt>{html.escape(qa["question"])}<span class="src">[{html.escape(qa["source"])}]</span></dt>'
            f'<dd>{html.escape(qa["answer"])}</dd>'
            for qa in qa_pairs
        )
        qa_html = f'<div class="card"><h3>Predicted screening Q&amp;A</h3><dl class="qa">{items}</dl></div>'

    body = f"""
    <a class="backlink" href="/">&larr; back to dashboard</a>
    <div class="card">
      <h1>{html.escape(job['title'])}</h1>
      <div class="sub">{html.escape(job['company'] or '')} &middot; {html.escape(job['portal'] or '')}
        &middot; {html.escape(job['location'] or '')} &middot; posted {html.escape(job['posted_date'] or 'unknown')}</div>
      <p class="score {_score_class(job['match_score'])}" style="font-size:20px">{job['match_score']:.2f} match</p>
      <p>{html.escape(job['match_reasoning'] or '')}</p>
      <div>
        <a class="btn" href="{html.escape(job['apply_url'])}" target="_blank">Open posting / apply</a>
        {resume_link}
        <button class="{apply_btn_cls}" onclick="markApplied({job_id}, this)">{apply_btn_label}</button>
      </div>
    </div>
    {qa_html}
    <script>
      function markApplied(id, btn) {{
        fetch('/api/mark-applied/' + id, {{method: 'POST'}}).then(() => {{
          btn.textContent = 'Marked applied';
          btn.className = 'btn applied';
        }});
      }}
    </script>
    """
    return _page(job["title"], body)


class Handler(BaseHTTPRequestHandler):
    # A fresh JobsDB (and thus a fresh sqlite3 connection) is opened per
    # request rather than shared across the ThreadingHTTPServer's worker
    # threads - sqlite3 connections are only usable on the thread that
    # created them, confirmed by a live ProgrammingError when a single
    # shared connection was tried here.

    def log_message(self, fmt, *args):
        pass  # keep stdout quiet - errors still raise normally

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        db = JobsDB()

        if not parts:
            self._send(200, render_index(db), "text/html")
        elif parts[0] == "job" and len(parts) == 2 and parts[1].isdigit():
            content = render_job(db, int(parts[1]))
            if content is None:
                self._send(404, b"Job not found", "text/plain")
            else:
                self._send(200, content, "text/html")
        elif parts[0] == "resume" and len(parts) == 2 and parts[1].isdigit():
            r = db.conn.execute(
                "SELECT tailored_resume_path FROM jobs WHERE id = ?", (int(parts[1]),)
            ).fetchone()
            path = Path(r[0]) if r and r[0] else None
            if path and path.exists():
                self._send(200, path.read_bytes(), "application/pdf")
            else:
                self._send(404, b"No resume on file for this job", "text/plain")
        else:
            self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "mark-applied" and parts[2].isdigit():
            db = JobsDB()
            db.conn.execute("UPDATE jobs SET status = 'applied' WHERE id = ?", (int(parts[2]),))
            db.conn.commit()
            self._send(200, json.dumps({"ok": True}).encode(), "application/json")
        else:
            self._send(404, b"Not found", "text/plain")

    def _send(self, code: int, body: bytes, content_type: str):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Job dashboard running at http://localhost:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
