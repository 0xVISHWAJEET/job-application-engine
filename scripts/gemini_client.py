"""
Minimal, dependency-free Gemini text-generation client (stdlib urllib only -
no venv/pip available in this environment, and this project's scripts don't
need anything heavier than one text-in/text-out call). Reads GOOGLE_API_KEY
from the environment - export it, or run scripts with:
  GOOGLE_API_KEY=$(grep GOOGLE_API_KEY ../VishuGPT/.env | cut -d= -f2) python3 script.py
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# The free tier's real, observed limit for this model is ~15 requests/min -
# discover_jobs.py scores dozens of listings back to back, so retrying with
# the API's own "Please retry in Xs" hint (rather than a fixed backoff) is
# what keeps a long discovery run from silently dropping most of its
# listings to 429s instead of just running a bit slower.
MAX_RETRIES = 5


class GeminiError(RuntimeError):
    pass


def generate(prompt: str, model: str | None = None) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("GOOGLE_API_KEY is not set in the environment.")

    url = API_URL_TEMPLATE.format(model=model or MODEL, key=api_key)
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")

    last_error = None

    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            last_error = GeminiError(f"Gemini API error {exc.code}: {body[:500]}")

            if exc.code != 429 or attempt == MAX_RETRIES - 1:
                raise last_error from exc

            wait_match = re.search(r"retry in ([\d.]+)s", body)
            wait_seconds = float(wait_match.group(1)) + 1 if wait_match else 10
            time.sleep(wait_seconds)
    else:
        raise last_error

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as exc:
        raise GeminiError(f"Unexpected Gemini response shape: {data}") from exc
