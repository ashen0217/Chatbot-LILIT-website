# Copilot instructions for this repository

## Build, run, and test commands

Use the commands already documented in `README.md` and project notes:

```bash
# environment setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# build/update knowledge base (required before running server)
python indexer.py

# run backend
uvicorn server:app --reload
# (alternative used in repo docs)
python server.py
```

Single-test command currently used in this repo:

```bash
python test_objectives_fix.py
```

There is no dedicated lint command/config checked into this repository (no `pyproject.toml`, `ruff.toml`, `pytest.ini`, etc.).

## High-level architecture

- This is a **RAG chatbot** for LILIT LMS with a static frontend (`index.html`) and FastAPI backend (`server.py`).
- `indexer.py` builds `faiss_db` from:
  - local files in `docs/**/*.txt` and `docs/**/*.pdf`
  - crawled content from `https://lms.lilit.lk/` plus hardcoded critical URLs
- `server.py` loads FAISS at startup with `OpenAIEmbeddings("text-embedding-3-small")` and serves:
  - `GET /` → `index.html`
  - `POST /chat` → **streaming SSE-style response** (`data: {"token": ...}` + `data: [DONE]`)
- `index.html` uses `fetch("http://127.0.0.1:8000/chat")` and incrementally renders streamed tokens from the backend.

## Key codebase conventions

- **Domain guard first:** off-topic questions must be rejected early by `is_lilit_related_query()`.
- **Canonical off-topic text:** keep this exact baseline phrase when rejecting:
  - `I am sorry, the requested questions types are not included in my database`
- **Language matching is required:** responses should follow the user’s language (English/Sinhala/Tamil intent in prompt; Sinhala detection is used in special handlers).
- **Deterministic handlers for critical org content:** vision, mission, objectives, and “about” responses use hardcoded canonical data in `server.py` for completeness/accuracy instead of relying only on retrieved snippets.
- **Course responses use structured fallback data:** `get_all_course_details()` returns hardcoded course blocks (ID, duration, fee, overview) cached for fast responses.
- **Response protocol compatibility matters:** frontend expects token streaming and `[DONE]`; avoid changing this wire format unless frontend is updated together.
- **Indexer behavior is intentional:** `indexer.py` sets `USER_AGENT` before loader usage and rebuilds `./faiss_db` from scratch on each run.
