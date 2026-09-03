"""
MCP server exposing this toolkit's job-search/tailoring/vault operations as
tools - callable from any MCP client (Claude Code, Claude Desktop, or
VishuGPT itself via its own mcp_client.py). This is the "mcp server" piece
of job automate.md's spec: everything it does is the same safe,
human-in-the-loop pipeline as running the scripts directly - it does not
add any browser automation or auto-submit capability of its own.

Run:
    export GOOGLE_API_KEY=...
    python3 mcp_server.py                    # stdio transport (Claude Desktop/Code)
    python3 mcp_server.py --http 8090         # Streamable HTTP, for VishuGPT's
                                               # MCP_SERVERS config or any remote client
"""

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "vault"))

from match_score import score as score_job_description  # noqa: E402
from tailor_cv import tailor as tailor_resume  # noqa: E402
from vault import Vault  # noqa: E402

import json  # noqa: E402

PROFILE_PATH = Path(__file__).parent.parent / "profile" / "candidate_profile.json"

mcp = MCPServer("job-application-engine")


@mcp.tool()
def score_job(job_description: str) -> dict:
    """Score a job description against the candidate profile (0.0-1.0 fit)."""
    profile = json.loads(PROFILE_PATH.read_text())
    return score_job_description(job_description, profile)


@mcp.tool()
def tailor_cv(company: str, role: str, job_description: str) -> str:
    """
    Tailor the resume's summary and experience bullets to a specific job
    description (reordering/trimming/lightly rewording only - never
    inventing new claims) and compile it to PDF. Returns the PDF path.
    """
    pdf_path = tailor_resume(company, role, job_description)
    return str(pdf_path)


@mcp.tool()
def vault_get(question: str) -> str:
    """Look up a previously-saved answer to a job-application screening question."""
    answer = Vault().get(question)
    return answer if answer else f"No saved answer for: {question!r}"


@mcp.tool()
def vault_set(question: str, answer: str) -> str:
    """Save an answer to a job-application screening question for future reuse."""
    Vault().set(question, answer)
    return f"Saved: {question!r} -> {answer!r}"


@mcp.tool()
def vault_list() -> dict:
    """List every saved screening-question answer."""
    return Vault().all()


@mcp.tool()
def get_candidate_profile() -> dict:
    """Return the full structured candidate profile (contact info, experience, skills)."""
    return json.loads(PROFILE_PATH.read_text())


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=int(sys.argv[2]))
    else:
        mcp.run(transport="stdio")
