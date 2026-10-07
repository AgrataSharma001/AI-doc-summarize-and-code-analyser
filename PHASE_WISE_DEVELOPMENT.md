# Phase-wise development work

This is the execution checklist for the [project plan](PROJECT_PLAN.md). It assumes four students (A: project/architecture, B: API/security, C: extraction/code tools, D: agent/evaluation), 12 weeks, and about 10 hours per student per week. Assign names at kickoff. Planned work is 360 person-hours; the remaining 120 hours are reserve.

## Phase 0 — Kickoff and decisions (weeks 1–2, 20 hours)

**Lead:** A, with input from everyone. **Depends on:** current frontend and its API contract.

- [x] Define supported file types, input limits, privacy/retention policy, target users, and release criteria in `docs/phase0/MVP_SCOPE.md`; team sign-off is tracked on the Phase 0 board.
- [x] Map `Frontend/README.md` routes and response shapes in `docs/phase0/API_CONTRACT.md`; this MVP requires accounts for chat.
- [ ] Confirm the localhost demo setup and ₹0 budget. Compare local Qwen3 1.7B and, if memory permits, 4B on 20 representative inputs for answer quality, latency, and RAM use.
- [x] Build a self-authored semantic evaluation set with 40 document and 40 Python cases, including 30 held-out cases each, expected facts/findings, and reviewer rubric.
- [x] Create the local issue board, A–D owner assignments, branch/review rules, and architecture decision log in `docs/phase0/`.

**Exit:** Scope, budget, API shape, local model choice, and evaluation method are recorded. Model quality and latency are measured on the demo laptop.

## Phase 1 — Backend foundation and first vertical slice (weeks 3–4, 70 hours)

**Lead:** B. **Support:** A for frontend wiring, D for a basic model adapter. **Depends on:** phase 0 API and model decisions.

- [x] Create FastAPI application, settings, health endpoint, and local SQLite configuration. The Ollama HTTP adapter remains a separate agent task.
- [x] Define user, session, conversation, source-file, source-span, and result tables; add the initial Alembic migration.
- [x] Implement `/api/auth/session`, `/api/auth/signup`, `/api/auth/login`, and `/api/auth/logout` with Argon2 password hashes, server sessions, same-origin checks, rate limits, and configurable secure cookies. Conversation ownership checks follow with `/api/chat`.
- [x] Implement `/api/chat` multipart parsing with server-side file count/size/type checks and clear 4xx errors. Intake requires login, same-origin requests, and conversation ownership; responses acknowledge validation only, pending extraction/model integration.
- [ ] Add TXT and pasted-text intake plus one simple document answer through the model adapter.
- [ ] Connect the current frontend to these endpoints; test a real signup -> upload -> reply -> logout path.

**Exit:** A local same-origin vertical slice works. A user cannot read another user's conversation. Secrets stay in server configuration. This milestone precedes full document and code analysis.

## Phase 2 — Document extraction and source mapping (weeks 5–6, 50 hours)

**Lead:** C. **Support:** D for chunk boundaries. **Depends on:** phase 1 intake and database tables.

- [ ] Extract TXT and Markdown while preserving paragraphs/headings; handle encoding failures.
- [ ] Extract text-based PDF pages with pypdf and DOCX paragraphs/headings/tables with python-docx.
- [ ] Save stable source IDs, page/section locations, and original ordering for every extractable span.
- [ ] Detect empty/image-only PDFs, corrupted files, oversized extracted text, and unsupported types; return actionable errors.
- [ ] Chunk long documents by structure; evaluate retrieval by checking that known answer spans are selected.
- [ ] Disable image uploads in the frontend until OCR/vision is implemented.

**Exit:** A test corpus extracts with resolvable references; an image-only PDF is reported as unsupported rather than summarized as empty text.

## Phase 3 — Team-built agent and Python analysis (weeks 6–8, 70 hours)

**Lead:** D for agent; C for code tools. **Depends on:** source mapping from phase 2. Some code-tool work can run alongside document extraction.

- [ ] Implement a bounded state machine: classify request -> select evidence -> model call -> schema validation -> citation validation -> response.
- [ ] Expose read-only source-span and Python-symbol tools. Keep model provider calls behind one replaceable adapter.
- [ ] Add document summary and document Q&A prompts, including insufficient-evidence behavior and one bounded retry for malformed output.
- [ ] Parse Python with `ast` and `tokenize` to identify functions/classes and accurate line numbers; run Ruff as a separate static check without executing user code.
- [ ] Add code explanation and review prompts. Label findings as potential issues, with severity, location, and reasoning.
- [ ] Persist source context on the server for follow-up questions; validate that conversation IDs belong to the signed-in user.
- [ ] Record request timing, token use, route, validation failures, and memory pressure without logging raw uploads by default.

**Exit:** Document and Python workflows return structured, source-grounded results. The agent cannot run shell commands, write files, browse externally, or execute uploads.

## Phase 4 — Full integration and quality (weeks 8–10, 95 hours)

**Leads:** A for UI (30 hours); B/C/D for quality and security (65 hours). **Depends on:** phases 1–3.

- [ ] Show summaries, code findings, source references, uncertainty, loading progress, and clear errors in the frontend.
- [ ] Add a server-side conversation deletion route and UI action; remove its stored source spans and results under the signed-in user's ownership.
- [ ] Test signup/login/logout, upload validation, follow-up questions, expired context, cancellation behavior, and cross-user isolation.
- [ ] Run unit and API integration tests, existing frontend smoke test, and browser tests against the real API.
- [ ] Test malformed uploads, MIME/extension mismatch, prompt injection inside files, and output containing HTML/script markup.
- [ ] Score a held-out set with two reviewers: factual support, citation validity, and actionable code findings. Resolve disagreement and report sample sizes.
- [ ] Measure latency and peak RAM use; tune chunking and token limits for the 8 GB or smaller laptop.

**Exit:** The measured release gates in `PROJECT_PLAN.md` are met or the exceptions are documented and scoped for correction. High-severity auth, upload, or cross-user defects block release.

## Phase 5 — Deployment, release, and handover (weeks 10–12, 55 hours)

**Lead:** A and B; all students contribute to the report. **Depends on:** phase 4 release candidate.

- [ ] Package a repeatable localhost startup for the API, SQLite, static frontend, and local model server.
- [ ] Add CI for Python tests, frontend smoke test, and migrations. Keep local configuration out of source control.
- [ ] Test on the target laptop, run migrations and end-to-end smoke tests, then tag the tested commit for the demo.
- [ ] Set localhost-only binding, cookie/Origin protection, request limits, health checks, logs, backup, and rollback procedure.
- [ ] Verify a fresh user's complete journey: signup, upload, answer, follow-up, logout, and deletion of retained content.
- [ ] Prepare architecture diagram, test/evaluation results, known limitations, runbook, final report, and demo script.

**Exit:** A working localhost demo and reproducible setup instructions exist. The team has rehearsed rollback and can explain the agent's control flow and measured limitations.

## Optional work, only after core release gates

- OCR or vision for scanned PDFs and PNG/JPG/WEBP; then re-enable image upload in the UI.
- JavaScript/TypeScript support with language-aware parsing and a new evaluation set.
- Embedding-based retrieval if keyword/section retrieval misses relevant evidence in long files and the laptop can support the extra model/index.
- Export and cross-device history after retention and deletion behavior are settled.

## Weekly management rhythm

Maintain one-week sprints, two short stand-ups, and a Friday demo. Each issue needs an owner, estimate, dependency, and observable acceptance check. Review the [risk register](PROJECT_PLAN.md#risk-calculation-and-response) every week; use the 120-hour reserve for defects on the critical path before optional features.
