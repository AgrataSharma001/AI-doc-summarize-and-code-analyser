# GenAI-Based Document Summarizer and Code Analyzer

A B.Tech Computer Science team project for understanding documents and source code through a web interface. Users will upload a file or paste content, request a summary or code analysis, and ask follow-up questions grounded in the supplied source.

## Current status

The repository has a working **frontend** in `Frontend/` and a **FastAPI backend** in `backend/`. The backend supports accounts, validated text uploads, and source-grounded answers through local Ollama. TXT, Markdown, pasted text, and Python source are stored as spans with stable IDs and line references; follow-up questions use server-held sources and successful turns. Citations are checked against the evidence supplied to the model. Conversation access expires after 24 hours, with cleanup on startup and every minute. The live signup -> TXT upload -> cited answer -> follow-up -> logout path has passed against FastAPI and Ollama; see [P1-05 evidence](docs/phase1/LIVE_INTEGRATION.md). PDF/DOCX extraction now preserves PDF page/line locations and DOCX heading, paragraph, and table-cell locations. TXT/Markdown extraction now respects paragraph/heading boundaries, and evidence selection also matches section labels; see [P2-02 evidence](docs/phase2/TEXT_RETRIEVAL.md). An explicit bounded agent now routes document summary/Q&A and code explanation/review, selects evidence, and validates answers before persistence; see [P3-01 evidence](docs/phase3/AGENT_WORKFLOW.md). Code-mode evidence now includes bounded AST/tokenize symbol outlines and syntax diagnostics; see [P3-02 evidence](docs/phase3/PYTHON_TOOLS.md). Code requests also run bounded, non-executing Ruff checks with structured potential findings and coverage warnings; see [P3-03 evidence](docs/phase3/RUFF_CHECKS.md). Code responses now combine schema-validated model findings with Ruff results, retaining provenance and source/line bounds; see [P3-04 evidence](docs/phase3/MODEL_FINDINGS.md). Live model reasoning still requires quality evaluation. Broader live model quality and performance still require the demo-laptop evaluation. The implementation sequence is in [PHASE_WISE_DEVELOPMENT.md](PHASE_WISE_DEVELOPMENT.md), and the full schedule and risk model are in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## MVP scope

| Area | Planned behavior |
|---|---|
| Document input | Pasted text, TXT, Markdown, text-based PDF, and DOCX |
| Document output | Brief or detailed summary, key points, and source page/section references where available |
| Code input | Pasted Python or a `.py` file |
| Code output | Purpose and flow explanation, function/class outline, potential issues, and file/line references |
| Follow-up | Questions answered using server-held conversation context |
| Accounts | Signup, login, logout, and private conversation ownership |

The current picker supports TXT/Markdown, text-based PDF, and DOCX in document mode and Python in code mode. Images and scanned PDFs need OCR or vision support. Uploaded code is inspected as text and is never executed.

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

`backend/sources.py` extracts and selects text spans, `backend/documents.py` extracts PDFs and DOCX, `backend/ollama.py` implements local model calls, and `backend/retention.py` removes expired context. `backend/agent.py` controls routing and validation using the shared schema in `backend/answers.py`; `backend/source_tools.py` exposes scoped read-only source/symbol tools, and `backend/python_analysis.py` performs non-executing Python structure inspection. `backend/ruff_analysis.py` runs isolated Ruff stdin checks and returns bounded, source-mapped potential findings.

## Run the current backend locally

From the repository root, with Python installed:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirement.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000/`. The initial Alembic migration runs on startup. `GET /health` checks SQLite, not model availability. Sign up or log in before sending chat requests. The frontend's expected endpoints and payloads are documented in [Frontend/README.md](Frontend/README.md).

Install Ollama separately and prepare the candidate model:

```powershell
ollama pull qwen3:1.7b
ollama serve
```

If Ollama is already running, use that instance. Keep its API on loopback. The backend defaults to `http://127.0.0.1:11434` and `qwen3:1.7b`; `.env.example` documents model, timeout, and context overrides. The model is a provisional candidate until the hardware benchmark is completed; no weights are downloaded by the application.

Upload a TXT/Markdown file (UTF-8, BOM-marked UTF-16/UTF-32, or Windows-1252), text-based PDF, or DOCX and ask for a summary, or paste source text into a new chat. PDF references use page/line numbers; DOCX references use body headings, paragraph numbers, and table cells rather than rendered page numbers. Blank PDF pages are reported as omitted; image-only files need OCR. DOCX images, text boxes, headers/footers, and tracked changes may be omitted and are disclosed in the answer. The first message without an attachment is treated as source text and summarized (or explained in code mode). Later messages are questions about retained sources. To add pasted content to an existing conversation, begin the message with `Source:` followed by a newline. A new source is added without extending the conversation's expiry. Long sources use selected excerpts and display a coverage warning; they are not yet summarized chunk by chunk. Citation validation checks references, not factual correctness.

The model adapter uses structured, non-streaming [Ollama chat requests](https://docs.ollama.com/api/chat), retries malformed output once, and returns controlled 502/503/504 errors. Failed model requests save no new input or answer, so retry with the retained browser draft/files. Only one model request runs at a time; others receive 429. Content access ends at expiry, and physical cleanup follows within the next minute while the server is running (or on its next startup). Clearing browser chat history currently does not delete server content before expiry.

Run backend tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

The existing browser smoke test mocks API responses and requires Node.js and Playwright:

```powershell
node Frontend/tests/smoke.cjs
```

This test does not verify a real backend or model. The separate `Frontend/tests/live.cjs` test verifies the real TXT workflow, retained-source follow-up, and logout. See [browser verification](Frontend/README.md#browser-verification) for setup and [recorded results](docs/phase1/LIVE_INTEGRATION.md).

## API contract

- `POST /api/chat`: multipart `mode`, `message`, `conversation_id`, `history`, and repeated `files`; returns `status: answered`, `reply` with source references, `source_ids`, `sources`, `warnings`, and new file metadata. Requires an active session and same-origin `Origin` or `Referer`. Supports `.txt`/`.md`/`.pdf`/`.docx` in document mode and `.py` in code mode. PDF/DOCX errors return 422 for unreadable/empty/encrypted inputs and 413 for extraction limits. PDFs are limited to 200 pages, 4 MiB per decoded page content stream, and 20 MiB of decoded page streams in total; parser decompression limits are also enforced. DOCX packages are capped at 1,000 entries, 20 MiB expanded data, and 10,000 visited blocks, with bounded nesting and source-location length. Limits: five files, 10 MiB combined, 200,000 message/source characters, 500,000 source characters per conversation, 256 KiB browser history, and a 12 MiB multipart body. TXT/Markdown accepts UTF-8, BOM-marked UTF-16/UTF-32, and Windows-1252; Python files must be UTF-8. MIME/content mismatches and binary control characters are rejected. Conversations expire after 24 hours and cannot switch mode. Browser history is validated and discarded; model history comes from the database. Chat is limited to 20 attempts per user per minute.
Code-mode responses additionally return `findings` (model and Ruff potential issues with tool provenance, severity, file/line references, reasoning, and source IDs), `analysis.checks` (per-file checker status and truncation), and `analysis.model_review` (schema/reference validation status and finding count). Model findings use line/end_line; Ruff findings also supply rule/column. Findings are appended to the reply and retained as an analysis result on successful requests. Review replies use a neutral server summary; explanation replies retain model prose. Reference validation does not establish that a finding is correct. These checks use fixed F/B/S rules; incomplete checks produce coverage warnings, and an empty findings list does not establish correctness.

- `GET /api/auth/session`: returns the current user or `null`.
- `POST /api/auth/signup`, `/api/auth/login`, `/api/auth/logout`: manage an HttpOnly server session backed by SQLite. Same-origin `Origin` or `Referer` is required for these POST requests.

Serve the frontend and API from the same origin. The server must enforce file limits and conversation ownership; it must not trust browser-provided history or filenames. Keep the local model endpoint bound to loopback and accessible only through the backend.

## Delivery plan

The working assumption is **four students over 12 weeks**, with 360 planned person-hours and a 120-hour reserve. The budget is **₹0** for inference and hosting, the available laptop has **8 GB RAM or less**, and server-held uploads/context expire after **24 hours**. The critical sequence is API/auth and extraction, source mapping, agent implementation, integration, evaluation, then deployment. See [PHASE_WISE_DEVELOPMENT.md](PHASE_WISE_DEVELOPMENT.md) for phase-by-phase tasks and acceptance checks.

## Responsible use

AI-generated summaries and code findings are aids to understanding. They can be incomplete or wrong. The interface should show source references and uncertainty, and users should verify important claims against the original files. Uploaded text is treated as untrusted data, including instructions embedded inside a document or code comment.
