# GenAI-Based Document Summarizer and Code Analyzer — project plan

## Planning assumptions and current baseline

- Team: four B.Tech Computer Science students, about 10 hours per person per week, for 12 weeks. Capacity is **480 person-hours**; plan **384 hours** of work and hold **96 hours (20%)** for risk and rework.
- The repository contains a static HTML/CSS/JavaScript frontend. `Frontend/README.md` defines the same-origin chat and authentication API. There is no working backend or populated dependency manifest yet.
- “Build our own agent” means implement our own bounded orchestration, tools, state, validation, and evaluation around a replaceable LLM. Training a foundation model is outside the semester scope.
- Deploy a demonstrable, low-traffic application. Confirm the hosting provider and model budget during week 1; do not assume a free tier or a fixed token price.

## Outcome and scope

**MVP:** A user can sign in, upload a TXT, Markdown, text-based PDF, DOCX, or Python file (or paste text/code), request a document summary or Python code explanation, and ask follow-up questions. Responses include source page/section or file/line references when extraction preserves them. The user sees useful extraction and model errors. Uploaded code is never executed.

**Stretch:** OCR for image uploads and scanned PDFs; JavaScript code analysis; export; persistent cross-device history. The existing frontend currently permits PNG/JPG/WEBP, so disable those file types in the UI until OCR or vision processing is implemented. Keep its current five-file/10 MiB total limit and enforce the same limits server-side.

**Acceptance targets (team-defined, measured on a held-out set):**

| Measure | Release target | How to measure |
|---|---:|---|
| Uploads and chat | 100% of supported happy-path test cases complete | API and browser integration tests |
| Document factual accuracy | At least 85% of sampled factual claims supported by cited source spans | Two human reviewers, 30 varied documents |
| Citation validity | At least 95% of emitted references resolve to a stored source span | Automated reference check |
| Code finding precision | At least 75% of flagged issues judged actionable | Two reviewers, 30 Python samples including known bugs |
| Unsafe code execution | Zero execution paths for user code | Code review and adversarial tests |
| Response reliability | At least 95% of ordinary requests complete without server errors | 100-request staging run |

The quality percentages are proposed release gates, not claims about current performance. Track reviewer disagreement and report results with sample sizes.

## Architecture

```text
Browser (existing static frontend)
  -> HTTPS, same-origin FastAPI application
  -> auth/session + upload validation + per-user conversation ownership
  -> document/code extraction with stable source IDs and locations
  -> bounded agent state machine
       classify request -> select evidence -> call model -> validate output
       -> verify citations -> retry once or return qualified result
  -> PostgreSQL (users, sessions, conversations, source spans, results)
  -> replaceable LLM provider adapter (credentials only on server)
```

Store only what follow-up questions need, with a configurable retention period and a delete operation. The server, not browser-supplied `history`, is the authority for conversation ownership and source context. For a small MVP, retrieval can start with keyword/section matching over stored spans. Add embeddings and pgvector only if evaluation shows a need for semantic retrieval across long documents; this avoids an unnecessary service and indexing pipeline in the first release.

## Recommended technology stack

| Layer | Choice | Reason / decision point |
|---|---|---|
| UI | Keep existing HTML, CSS, vanilla JavaScript | Integration work is smaller than a framework rewrite. |
| API | Python 3.12+, FastAPI, Pydantic | Typed multipart API, validation, OpenAPI documentation. |
| Document extraction | `pypdf` for text PDFs, `python-docx` for DOCX, standard Python for TXT/Markdown | Retain page/heading metadata; explicitly reject image-only PDFs until OCR exists. |
| Code inspection | Python `ast`, `tokenize`, `ruff` as a separate non-executing check | Deterministic structure and line locations complement LLM explanations. Start with Python only. |
| Agent/LLM | Team-authored Python state machine and provider interface; one hosted model selected by a week-2 quality/cost/latency spike | Makes routing and checks visible for the project defense. Pin model ID in config. |
| Storage | PostgreSQL; local Docker Compose for development | Required for accounts, server-held context, and ownership. Add pgvector only after a retrieval benchmark. |
| Security | Argon2 password hashing, server-side sessions, HttpOnly/Secure/SameSite cookies, CSRF/Origin checks, upload limits | Matches the existing frontend's authentication contract. |
| Tests/ops | `pytest`, frontend smoke test, Playwright browser tests, GitHub Actions, Docker, structured logs | Covers API behavior, UI workflow, deployment, and diagnosis. |
| Hosting | One managed container service for the API/static assets plus managed PostgreSQL | Same-origin routing simplifies cookies and uploads. Choose vendor in week 1 based on budget and region. |

Avoid putting model API keys in the browser. Record per-request token usage, latency, and estimated cost without logging document contents by default.

## Agent design and tasks

The agent is a deterministic controller with **bounded** model use, not an unrestricted autonomous process.

1. **Intake tool:** validate file count, total size, extension, MIME/content signature, and text extraction. Assign immutable source IDs and page/line metadata.
2. **Router:** select `document_summary`, `document_qa`, `code_explanation`, or `code_review` from the explicit UI mode and request. Reject ambiguous or unsupported content with a clear message.
3. **Evidence selector:** chunk by sections/pages or Python functions, then select relevant spans. For long documents, summarize chunks and synthesize an overall summary from those summaries plus references.
4. **Analysis tools:** expose read-only `get_source_span`, `list_sections`, and `get_python_symbols`; optionally run Ruff as a separate static checker. Never expose shell, network, file write, or user-code execution tools to the model.
5. **Model adapter:** use typed requests and structured output containing answer, claim/support IDs, code findings, severity, and uncertainty. Keep prompt templates versioned.
6. **Validator:** enforce schema, reference ownership, source-ID existence, and line/page bounds. Retry a malformed answer once; if evidence is insufficient, return an explicit limitation.
7. **Telemetry and evaluation:** record route, retrieval IDs, validation failures, latency, token use, and reviewer scores. Redact or omit sensitive content in logs.

Treat uploaded text as data, even when it contains instructions such as “ignore previous directions.” Keep agent instructions and user content in separate roles. The model may suggest code changes, but the application never applies or runs them automatically.

## Work breakdown, ownership, and deliverables

Choose a primary owner for each stream; every merge request gets review from another student. Owners can pair on blocking integration work.

| Stream (owner) | Detailed tasks | Deliverable / completion check | Planned hours |
|---|---|---|---:|
| Product and architecture (student A, project lead) | Confirm MVP, choose hosted model/provider with 20-file spike, design DB and API schemas, create evaluation rubric and issue board | Architecture and API decisions recorded; sample set and release gates agreed | 20 |
| API and auth (student B) | FastAPI skeleton; `/api/chat` multipart contract; session/login/signup/logout; password hashing; ownership; size/rate limits; migrations | Existing frontend can sign in and make a basic chat request; API tests pass | 75 |
| Extraction and code tools (student C) | TXT/Markdown/PDF/DOCX parsing; source map and text quality checks; Python AST symbols; Ruff integration; malformed-file errors | Test corpus produces stable page/line IDs; no code execution | 55 |
| Agent and evaluation (student D, AI lead) | Agent state machine; provider adapter; prompts; chunking and evidence selection; response schema; citation validation; evaluation harness | Grounded summaries/analyses with measured quality and one bounded retry | 75 |
| Frontend integration (students A+B) | Connect real endpoints, display source references and failures, disable unsupported image types, accessible loading/progress states | Browser end-to-end happy path and error path work | 35 |
| Security and quality (students B+C+D) | Unit/integration/browser tests; prompt-injection and cross-user tests; reviewer scoring; latency/cost profiling; accessibility checks | Release gates met or exceptions documented | 70 |
| Deployment and report (students A+B, all contribute) | Docker, managed DB, migrations, CI/CD, staging and production, rollback/backup, setup guide, architecture diagram, demo and final report | Public/demo URL, reproducible release, test results, project report | 54 |
| **Total planned** | | | **384** |

## 12-week schedule and gates

| Week | Focus | Exit gate |
|---|---|---|
| 1 | Scope, baseline repo audit, hosting/model budget, privacy/retention decisions, issue board | MVP and constraints signed off by team |
| 2 | API contract tests, DB schema, model spike, evaluation corpus | Provider selected from measured quality, latency, and cost |
| 3 | FastAPI scaffold, local Postgres, auth/session skeleton, file validators | Local same-origin frontend-to-API request works |
| 4 | Complete auth/ownership, TXT/Markdown/Python intake, first agent route | Vertical slice: login -> upload -> answer |
| 5 | PDF/DOCX extraction, source mapping, chunking | Supported files have verifiable locations |
| 6 | Document summary and document Q&A with citations | Document workflow passes first evaluation round |
| 7 | Python AST/Ruff checks, code explanation/review | Code workflow passes first evaluation round |
| 8 | Frontend integration, consistent errors, follow-up state | Full user flow works in staging |
| 9 | Adversarial/security tests, prompt and retrieval tuning | Cross-user isolation and upload tests pass |
| 10 | Performance/cost tests, deployment pipeline, backup and rollback drill | Release candidate and operational checklist |
| 11 | Buffer, defect fixes, optional OCR if all core gates pass | Release gates measured on held-out corpus |
| 12 | Final deployment, demo rehearsal, report, handover | Demo and reproducible documentation |

**Critical path:** API/auth and file extraction -> source IDs -> agent evidence selection/validation -> frontend integration -> evaluation -> deployment. OCR, extra languages, and vector search must not displace this path.

## Deployment phases

1. **Local (weeks 3–4):** Docker Compose runs API and PostgreSQL; serve `Frontend/` from the API origin. Provide `.env.example`, seed/demo account procedure, and migrations.
2. **Staging (weeks 8–10):** Build a pinned container image in GitHub Actions, run tests, deploy to a managed container service with a separate managed database, set secrets in the host, enforce HTTPS, run migrations, and perform smoke tests.
3. **Production/demo (weeks 11–12):** Promote the tested image, set upload/body/time limits and model spend alerts, verify health endpoint and logs, back up DB, and rehearse rollback to the previous image. Use a dedicated demo account and non-sensitive sample files.

Deployment is complete when a fresh user can sign up, upload a supported file, get a referenced answer, ask a follow-up, log out, and delete retained content without developer intervention.

## Risk calculation and response

Use a simple **expected effort exposure**: probability × impact in person-days (one person-day = 8 hours). These are planning estimates, not statistical forecasts. Re-estimate weekly from actual incidents.

| Risk | Probability | Impact | Exposure | Trigger and response |
|---|---:|---:|---:|---|
| Model hallucinations or invalid citations | 40% | 7 days | 2.8 days | Citation score below 95%; improve span selection and validator, narrow answer scope |
| PDF/DOCX extraction failures | 35% | 6 days | 2.1 days | More than 10% of corpus extracts poorly; reject unsupported layouts clearly, defer OCR |
| API/model cost or quota pressure | 30% | 5 days | 1.5 days | Spend forecast exceeds budget; shorten context, cache safe repeated work, cap requests |
| Auth/upload security defect | 25% | 6 days | 1.5 days | Cross-user or malicious-upload test fails; stop release, fix ownership/validation |
| Team integration delay | 30% | 5 days | 1.5 days | Vertical slice misses week 4; pair on critical path, cut stretch features |
| Deployment/hosting issue | 25% | 4 days | 1.0 day | Staging unavailable or migration fails; use pinned image, backup, rollback rehearsal |
| **Total expected exposure** | | | **10.4 person-days = 83.2 hours** | **96-hour reserve leaves 12.8 hours beyond this estimate** |

These exposures can overlap, so their sum is a workload planning indicator, not a guaranteed calendar delay. Review the top three risks at each weekly stand-up. Escalate any risk that threatens a release gate or consumes more than half the reserve.

## Management cadence and immediate next actions

- Use one-week sprints, a 15-minute stand-up twice weekly, one demo each Friday, and an issue board with owner, estimate, acceptance test, and status.
- Keep the main branch releasable. Require one review and passing CI before merge. Maintain an architecture decision log and a small set of demo files with expected answers.
- First actions: assign the four stream owners; set a model/hosting budget; create 20 representative files and 10 Python examples; implement a FastAPI `/api/chat` stub matching `Frontend/README.md`; run the existing frontend smoke test; schedule the week-4 vertical-slice demo.

## Reference documentation

- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [OpenAI developer quickstart and agent integration](https://platform.openai.com/docs/quickstart/make-your-first-api-request)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [GitHub Actions Docker publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)
- [OWASP LLM application risks](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
