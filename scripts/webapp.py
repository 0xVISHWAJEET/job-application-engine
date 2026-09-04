"""
Dashboard for jobs.db - browse every qualifying job (score >= 0.80, posted
within the last 30 days) in one page: portal, company, role, match score/
reasoning, a link to the tailored resume PDF, the apply URL, and the
predicted Q&A for that posting. This is personal data (real resume/contact
info, Q&A answers about visa status etc.) - when reverse-proxied publicly
(see gateway-live-aspireztech/Caddyfile's /vishujob route), it's gated
behind HTTP basic auth, never left open.

Usage:
    python3 scripts/webapp.py [port]   # default port 8095
    -> open http://localhost:8095 in a browser

Set BASE_PATH (e.g. "/vishujob") when this is reverse-proxied under a path
prefix that the proxy strips before forwarding (Caddy's handle_path does
this) - every link/fetch URL this page generates needs that prefix added
back in, since the browser resolves root-relative hrefs against the full
domain, not against whatever prefix stripping happened upstream.

Visual design: styled as an ops console (status-light colors, monospace
data readouts, a tilted-card pipeline readout in the header) rather than a
generic admin-table look, since the audience is an infra engineer and the
tool's own job is literally running a discover -> score -> tailor
pipeline - the header visualization shows that pipeline's real live
counts, not decoration.
"""

import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent / "jobs"))
from jobs_db import JobsDB  # noqa: E402

DEFAULT_PORT = 8095
MIN_SCORE = 0.80
BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")

STYLE = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    color-scheme: dark;
    --bg: #0a0d12;
    --surface: #10141b;
    --surface-raised: #171d27;
    --border: #232a37;
    --text: #e8ecf3;
    --text-dim: #7c8698;
    --signal: #00e0a4;
    --signal-glow: rgba(0, 224, 164, .35);
    --pulse: #7c8fff;
    --pulse-glow: rgba(124, 143, 255, .35);
    --amber: #ffb454;
    --font-display: "Space Grotesk", system-ui, sans-serif;
    --font-body: "Inter", system-ui, sans-serif;
    --font-mono: "JetBrains Mono", ui-monospace, monospace;
  }
  * { box-sizing: border-box; }
  body {
    font-family: var(--font-body); margin: 0; padding: 32px 40px 60px;
    background:
      radial-gradient(1200px 500px at 15% -10%, rgba(124,143,255,.08), transparent 60%),
      radial-gradient(900px 400px at 100% 0%, rgba(0,224,164,.06), transparent 55%),
      var(--bg);
    color: var(--text); min-height: 100vh;
  }
  a { color: var(--pulse); text-decoration: none; }
  a:hover { text-decoration: underline; }
  a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {
    outline: 2px solid var(--signal); outline-offset: 2px; border-radius: 4px;
  }

  .eyebrow {
    font-family: var(--font-mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase;
    color: var(--text-dim); display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  }
  .eyebrow .dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--signal);
    box-shadow: 0 0 8px var(--signal-glow); animation: blink 2.4s ease-in-out infinite;
  }
  h1.title {
    font-family: var(--font-display); font-weight: 700; font-size: 28px; margin: 0 0 6px;
    letter-spacing: -.01em;
  }
  .sub { color: var(--text-dim); margin-bottom: 28px; font-size: 13px; max-width: 62ch; line-height: 1.5; }

  /* ---- pipeline readout (signature 3D element) ---- */
  .pipeline { display: flex; align-items: center; gap: 0; margin: 32px 0 36px; perspective: 900px; }
  .pipeline-card {
    --tz: 0px;
    flex: 1; position: relative; background: linear-gradient(160deg, var(--surface-raised), var(--surface));
    border: 1px solid var(--border); border-radius: 14px; padding: 22px 24px;
    transform: rotateX(16deg) rotateY(-22deg) translateZ(var(--tz));
    transform-style: preserve-3d;
    transition: transform .45s cubic-bezier(.2,.8,.2,1), box-shadow .45s, opacity .5s;
    box-shadow: 26px 30px 45px -20px rgba(0,0,0,.75), 1px 1px 0 1px rgba(255,255,255,.02) inset;
    opacity: 0; animation: settle .6s ease-out forwards;
  }
  .pipeline-card:nth-child(1) { animation-delay: .05s; }
  .pipeline-card:nth-child(3) { --tz: -18px; animation-delay: .2s; }
  .pipeline-card:nth-child(5) { --tz: -36px; animation-delay: .35s; }
  .pipeline-card:hover {
    transform: rotateX(0deg) rotateY(0deg) translateZ(20px);
    box-shadow: 0 30px 50px -20px rgba(0,0,0,.8);
    z-index: 2;
  }
  @keyframes settle { from { opacity: 0; } to { opacity: 1; } }
  .pipeline-card::before {
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px; border-radius: 14px 14px 0 0;
    background: var(--edge, var(--signal)); box-shadow: 0 0 14px 0 var(--edge-glow, var(--signal-glow));
  }
  .pipeline-card .num {
    font-family: var(--font-mono); font-weight: 600; font-size: 34px; color: var(--edge, var(--signal));
    line-height: 1;
  }
  .pipeline-card .label {
    font-size: 12px; color: var(--text-dim); margin-top: 8px; text-transform: uppercase; letter-spacing: .08em;
  }
  .pipeline-flow {
    width: 56px; height: 2px; flex-shrink: 0; position: relative; margin: 0 -2px;
    background: linear-gradient(90deg, var(--border), var(--border));
    align-self: center; top: -2px;
  }
  .pipeline-flow::after {
    content: ""; position: absolute; top: -2px; left: 0; width: 14px; height: 6px; border-radius: 3px;
    background: var(--pulse); box-shadow: 0 0 10px var(--pulse-glow);
    animation: flow 2.6s linear infinite;
  }
  @keyframes flow { 0% { left: -14px; opacity: 0; } 15% { opacity: 1; } 85% { opacity: 1; } 100% { left: 56px; opacity: 0; } }
  @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }

  /* ---- filters ---- */
  .filters { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
  .filters input, .filters select {
    background: var(--surface); border: 1px solid var(--border); color: var(--text);
    padding: 9px 12px; border-radius: 8px; font-size: 13px; font-family: var(--font-body);
  }
  .filters input { flex: 1; min-width: 220px; }
  .filters input::placeholder { color: var(--text-dim); }

  /* ---- table ---- */
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  th {
    color: var(--text-dim); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
    position: sticky; top: 0; background: var(--bg); cursor: pointer; user-select: none;
  }
  th:hover { color: var(--text); }
  tbody tr { transition: background .15s; }
  tbody tr:hover { background: var(--surface); }
  .score { font-family: var(--font-mono); font-weight: 600; }
  .score.high { color: var(--signal); } .score.mid { color: var(--pulse); }
  .badge {
    display: inline-block; padding: 3px 9px; border-radius: 999px; font-size: 11px;
    background: var(--surface-raised); color: var(--text-dim); border: 1px solid var(--border); margin-right: 4px;
  }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }
  .dot.ready { background: var(--signal); box-shadow: 0 0 6px var(--signal-glow); }
  .dot.queued { background: var(--amber); }
  .status-applied { color: var(--signal); font-family: var(--font-mono); font-size: 12px; }
  .status-tailored, .status-scored { color: var(--text-dim); font-family: var(--font-mono); font-size: 12px; }
  .muted { color: var(--text-dim); }
  .mono { font-family: var(--font-mono); font-size: 12px; color: var(--text-dim); }

  /* ---- detail page ---- */
  .backlink { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 20px; font-family: var(--font-mono); font-size: 13px; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 26px; margin-bottom: 18px;
  }
  .score-readout {
    display: inline-flex; align-items: baseline; gap: 8px; padding: 10px 18px; border-radius: 10px;
    background: var(--surface-raised); border: 1px solid var(--border); margin: 14px 0;
    perspective: 600px;
  }
  .score-readout .val { font-family: var(--font-mono); font-weight: 600; font-size: 26px; }
  .score-readout .val.high { color: var(--signal); } .score-readout .val.mid { color: var(--pulse); }
  .score-readout .unit { color: var(--text-dim); font-size: 12px; }
  .reasoning { color: var(--text); line-height: 1.6; font-size: 14px; }
  .qa dt { font-weight: 600; margin-top: 16px; font-size: 14px; }
  .qa dd { margin: 5px 0 0; color: var(--text-dim); line-height: 1.55; font-size: 13.5px; }
  .src { font-family: var(--font-mono); font-size: 10px; color: var(--pulse); margin-left: 8px; text-transform: uppercase; }

  .btn {
    display: inline-block; padding: 10px 16px; border-radius: 8px; margin-right: 8px; font-size: 13px;
    background: var(--pulse); color: #0a0d12; font-weight: 600; border: none; cursor: pointer; font-family: var(--font-body);
  }
  .btn:hover { text-decoration: none; filter: brightness(1.1); }
  .btn.secondary { background: var(--surface-raised); color: var(--text); border: 1px solid var(--border); }
  .btn.applied { background: var(--signal); color: #0a0d12; }

  @media (max-width: 720px) {
    body { padding: 20px; }
    .pipeline { flex-direction: column; align-items: stretch; }
    .pipeline-flow { display: none; }
    table, thead, tbody, th, td, tr { display: block; }
    th { display: none; }
    td { border: none; padding: 4px 0; }
    tbody tr { border-bottom: 1px solid var(--border); padding: 12px 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .pipeline-card { animation: none; opacity: 1; }
    .pipeline-flow::after { animation: none; display: none; }
    .eyebrow .dot { animation: none; }
  }
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>{STYLE}</head><body>{body}</body></html>""".encode()


def _pipeline_readout(sources: int, scanned: int, qualifying: int) -> str:
    """The signature element: three tilted 3D cards (perspective + rotateX/Y,
    a resting isometric-ish lean that straightens on hover) reading the
    pipeline's actual live counts, connected by an animated flow line - not
    decoration, this is what discover_jobs.py is doing right now."""
    return f"""
    <div class="pipeline">
      <div class="pipeline-card" style="--edge: var(--pulse); --edge-glow: var(--pulse-glow)">
        <div class="num">{sources}</div>
        <div class="label">Sources wired in</div>
      </div>
      <div class="pipeline-flow"></div>
      <div class="pipeline-card" style="--edge: var(--amber); --edge-glow: rgba(255,180,84,.35)">
        <div class="num">{scanned}</div>
        <div class="label">Listings scanned</div>
      </div>
      <div class="pipeline-flow"></div>
      <div class="pipeline-card">
        <div class="num">{qualifying}</div>
        <div class="label">Qualifying (&ge;{MIN_SCORE:.0%})</div>
      </div>
    </div>
    """


def render_index(db: JobsDB) -> bytes:
    jobs = db.qualifying(min_score=MIN_SCORE, max_age_days=36500)  # dashboard shows all qualifying, age filter already applied at discovery time
    summary = db.summary()
    from ats_boards import COMPANY_BOARDS  # local import - avoids a hard dependency for callers that don't render the header
    source_count = len(COMPANY_BOARDS) + 9  # + the 9 direct-scrape sources (RemoteOK, WWR, Dice, ...)

    rows = []
    for j in jobs:
        score_cls = _score_class(j["match_score"])
        status_cls = f"status-{j['status']}" if j["status"] else ""

        has_resume = bool(j["tailored_resume_path"]) and Path(j["tailored_resume_path"]).exists()
        resume_cell = (
            f'<a href="{BASE_PATH}/resume/{j["id"]}" target="_blank"><span class="dot ready"></span>PDF</a>' if has_resume else
            '<span class="muted"><span class="dot queued"></span>queued</span>'
        )
        qa_count = len(db.get_questions(j["id"]))
        qa_cell = (
            f'<span class="dot ready"></span>{qa_count}' if qa_count else
            '<span class="muted"><span class="dot queued"></span>queued</span>'
        )

        rows.append(f"""
        <tr data-portal="{html.escape(j['portal'] or '')}" data-role="{html.escape(j['role_category'] or '')}">
          <td class="score {score_cls}">{j['match_score']:.2f}</td>
          <td><a href="{BASE_PATH}/job/{j['id']}">{html.escape(j['title'])}</a></td>
          <td>{html.escape(j['company'] or '')}</td>
          <td><span class="badge">{html.escape(j['portal'] or '')}</span></td>
          <td><span class="badge">{html.escape(j['role_category'] or '')}</span></td>
          <td class="mono">{html.escape(j['posted_date'] or '—')}</td>
          <td>{resume_cell}</td>
          <td>{qa_cell}</td>
          <td><a href="{html.escape(j['apply_url'])}" target="_blank">Apply &rarr;</a></td>
          <td class="{status_cls}">{html.escape(j['status'] or '')}</td>
        </tr>""")

    portals = sorted({j["portal"] for j in jobs if j["portal"]})
    roles = sorted({j["role_category"] for j in jobs if j["role_category"]})
    portal_opts = "".join(f'<option value="{html.escape(p)}">{html.escape(p)}</option>' for p in portals)
    role_opts = "".join(f'<option value="{html.escape(r)}">{html.escape(r)}</option>' for r in roles)

    empty_state = "" if jobs else """
    <div class="card" style="text-align:center; padding: 48px 26px;">
      <div class="eyebrow" style="justify-content:center"><span class="dot"></span>waiting on the pipeline</div>
      <p class="reasoning">No qualifying jobs yet - the scoring pass either hasn't run or hit a quota wall.
      Nothing to do here; check back once it's made progress.</p>
    </div>
    """

    body = f"""
    <div class="eyebrow"><span class="dot"></span>job-application-engine</div>
    <h1 class="title">Pipeline Console</h1>
    <div class="sub">{len(jobs)} qualifying jobs, score &ge; {MIN_SCORE:.2f}, posted within 30 days. "Queued" in
      Resume/Q&amp;A means the background pipeline hasn't reached that job yet - it processes sequentially,
      so a large batch takes a while. Refresh later.</div>
    {_pipeline_readout(source_count, summary['total'], summary['qualifying_80pct'])}
    {empty_state}
    <div class="filters">
      <input id="q" placeholder="Search title or company..." oninput="filterRows()">
      <select id="portalFilter" onchange="filterRows()"><option value="">All portals</option>{portal_opts}</select>
      <select id="roleFilter" onchange="filterRows()"><option value="">All roles</option>{role_opts}</select>
    </div>
    <table id="jobsTable">
      <thead><tr>
        <th onclick="sortBy(0)">Score</th><th onclick="sortBy(1)">Title</th><th onclick="sortBy(2)">Company</th>
        <th>Portal</th><th>Role</th><th onclick="sortBy(5)">Posted</th><th>Resume</th><th>Q&amp;A</th><th>Apply</th><th>Status</th>
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
    return _page("Pipeline Console", body)


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
        resume_link = f'<a class="btn secondary" href="{BASE_PATH}/resume/{job_id}" target="_blank">Open tailored resume (PDF)</a>'

    applied = job["status"] == "applied"
    apply_btn_label = "Marked applied" if applied else "Mark as applied"
    apply_btn_cls = "btn applied" if applied else "btn secondary"

    qa_html = ""
    if qa_pairs:
        items = "".join(
            f'<dt>{html.escape(qa["question"])}<span class="src">{html.escape(qa["source"])}</span></dt>'
            f'<dd>{html.escape(qa["answer"])}</dd>'
            for qa in qa_pairs
        )
        qa_html = f'<div class="card"><h3 style="font-family:var(--font-display); margin-top:0">Predicted screening Q&amp;A</h3><dl class="qa">{items}</dl></div>'

    score_cls = _score_class(job["match_score"])
    body = f"""
    <a class="backlink" href="{BASE_PATH}/">&larr; back to console</a>
    <div class="card">
      <div class="eyebrow">{html.escape(job['portal'] or '')}</div>
      <h1 class="title">{html.escape(job['title'])}</h1>
      <div class="sub">{html.escape(job['company'] or 'Unknown company')}
        &middot; {html.escape(job['location'] or 'location unspecified')}
        &middot; posted {html.escape(job['posted_date'] or 'date unknown')}</div>
      <div class="score-readout">
        <span class="val {score_cls}">{job['match_score']:.2f}</span>
        <span class="unit">/ 1.00 match</span>
      </div>
      <p class="reasoning">{html.escape(job['match_reasoning'] or '')}</p>
      <div>
        <a class="btn" href="{html.escape(job['apply_url'])}" target="_blank">Open posting &amp; apply</a>
        {resume_link}
        <button class="{apply_btn_cls}" onclick="markApplied({job_id}, this)">{apply_btn_label}</button>
      </div>
    </div>
    {qa_html}
    <script>
      function markApplied(id, btn) {{
        fetch('{BASE_PATH}/api/mark-applied/' + id, {{method: 'POST'}}).then(() => {{
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
