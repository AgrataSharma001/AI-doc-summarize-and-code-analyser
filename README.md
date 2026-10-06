# GenAI-Based Document Summarizer and Code Analyzer

A B.Tech Computer Science team project for understanding documents and source code through a web interface. Users will upload a file or paste content, request a summary or code analysis, and ask follow-up questions grounded in the supplied source.

## Current status

The repository has a working **frontend** in `Frontend/` and a **FastAPI backend** in `backend/`. The backend serves the frontend, checks SQLite health, and supports signup, login, session lookup, and logout. Uploads and AI replies are not implemented yet. `requirement.txt` includes dependencies for this foundation and later phases. The implementation sequence is in [PHASE_WISE_DEVELOPMENT.md](PHASE_WISE_DEVELOPMENT.md), and the full schedule and risk model are in [PROJECT_PLAN.md](PROJECT_PLAN.md). Phase 0 work is tracked in [the local board](docs/phase0/WORK_BOARD.md).

## MVP scope

| Area | Planned behavior |
|---|---|
| Document input | Pasted text, TXT, Markdown, text-based PDF, and DOCX |
| Document output | Brief or detailed summary, key points, and source page/section references where available |
| Code input | Pasted Python or a `.py` file |
| Code output | Purpose and flow explanation, function/class outline, potential issues, and file/line references |
| Follow-up | Questions answered using server-held conversation context |
| Accounts | Signup, login, logout, and private conversation ownership |

Scanned PDFs and PNG/JPG/WEBP need OCR or vision support. The current frontend accepts image files, so image upload must be disabled during integration until that support exists. Uploaded code will be inspected as text; it will not be executed.

## Planned architecture

```text
Browser (existing HTML/CSS/JavaScript)
  -> same-origin FastAPI API
  -> authentication + upload validation
  -> PDF/DOCX/text extraction or Python AST inspection
  -> team-built agent: route -> select source spans -> call LLM -> validate answer
  -> SQLite for users, sessions, conversations, and source spans
```

Our **own agent** is the Python control flow around a replaceable language model. It selects the appropriate workflow and evidence, requests a structured answer, checks cited source locations, and performs at most one retry for malformed output. It has read-only analysis tools and no tool that runs uploaded code. Training a foundation model is outside the project scope.

## Technology choices

| Layer | Planned technology |
|---|---|
| Frontend | Existing HTML, CSS, vanilla JavaScript |
| Backend | Python, FastAPI, Pydantic |
| Storage | SQLite, SQLAlchemy, Alembic migrations |
| Parsing | pypdf, python-docx, Python standard library |
| Python code analysis | `ast` and Ruff static checks |
| AI | Ollama on the team laptop, starting with Qwen3 1.7B; compare with Qwen3 4B if memory permits |
| Testing and deployment | pytest, existing frontend smoke test, GitHub Actions, team-hosted localhost demo |

Dependencies are listed in [requirement.txt](requirement.txt). Pin exact tested versions before the final demo release.

## Repository map

```text
Frontend/                  Existing static interface and frontend smoke test
backend/                   FastAPI, SQLite models, auth, and Alembic migrations
tests/                     Backend and migration tests
README.md                  Project overview and current status
requirement.txt             Planned Python dependencies
PHASE_WISE_DEVELOPMENT.md   Phase tasks, owners, and exit criteria
PROJECT_PLAN.md             Full architecture, timeline, measures, and risks
```

The upload, extraction, agent, and additional integration modules will be added in later phases.

## Run the current backend locally

From the repository root, with Python installed:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirement.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/`. The initial Alembic migration runs on startup. `GET /health` checks the SQLite connection; signup, login, session lookup, and logout now work through the frontend. Upload and AI requests still need the next backend tasks. The frontend's expected endpoints and payloads are documented in [Frontend/README.md](Frontend/README.md).

Run backend tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

The existing browser smoke test mocks API responses and requires Node.js and Playwright:

```powershell
node Frontend/tests/smoke.cjs
```

This test does not verify a real backend or model. See the test file header for browser setup options.

## API contract

- Planned `POST /api/chat`: multipart `mode`, `message`, `conversation_id`, `history`, and repeated `files`; responds with JSON containing `reply` or structured results.
- `GET /api/auth/session`: returns the current user or `null`.
- `POST /api/auth/signup`, `/api/auth/login`, `/api/auth/logout`: manage an HttpOnly server session backed by SQLite. Same-origin `Origin` or `Referer` is required for these POST requests.

Serve the frontend and API from the same origin. The server must enforce file limits and conversation ownership; it must not trust browser-provided history or filenames. Keep the local model endpoint bound to loopback and accessible only through the backend.

## Delivery plan

The working assumption is **four students over 12 weeks**, with 360 planned person-hours and a 120-hour reserve. The budget is **₹0** for inference and hosting, the available laptop has **8 GB RAM or less**, and server-held uploads/context expire after **24 hours**. The critical sequence is API/auth and extraction, source mapping, agent implementation, integration, evaluation, then deployment. See [PHASE_WISE_DEVELOPMENT.md](PHASE_WISE_DEVELOPMENT.md) for phase-by-phase tasks and acceptance checks.

## Responsible use

AI-generated summaries and code findings are aids to understanding. They can be incomplete or wrong. The interface should show source references and uncertainty, and users should verify important claims against the original files. Uploaded text is treated as untrusted data, including instructions embedded inside a document or code comment.
