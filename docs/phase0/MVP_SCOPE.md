# Phase 0, task 1: MVP scope and release agreement

**Status:** Draft for team sign-off. Derived from the existing frontend and `PROJECT_PLAN.md` on 2026-10-06. The user set a strict ₹0 budget, 24-hour server retention, a laptop with 8 GB RAM or less, and an acceptable localhost demo.

## Intended users and jobs

| User | Main job | MVP result |
|---|---|---|
| Student or researcher | Understand a long text document | Summary and follow-up answer with page/section evidence |
| Python learner or developer | Understand unfamiliar code | Function/class outline, behavior explanation, and located potential issues |

## In scope for the first release

1. Signed-in users can paste text or upload TXT, Markdown, text-based PDF, or DOCX for summarization and follow-up questions.
2. Signed-in users can paste Python or upload `.py` for explanation and review. Static checks and language parsing may supplement model output; uploaded code is never run.
3. Answers show source page/section or file/line locations when the parser can establish them. When evidence is insufficient, the answer says so.
4. Users can revisit context during the retention window and delete their server-held conversation and extracted source data.
5. The current frontend and API are served from one origin; authentication and file ownership are enforced on the server.

## Boundaries

| Boundary | First-release rule | Reason |
|---|---|---|
| Files per request | At most 5 | Matches the current frontend |
| Combined upload bytes | At most 10 MiB | Matches the current frontend; enforce during streaming on the server |
| Supported upload extensions | `.txt`, `.md`, `.pdf`, `.docx`, `.py` | Markdown is planned in the product scope; current picker needs `.md` added during integration |
| Scanned PDF or images | Reject with an explanation until OCR/vision is implemented | Existing photo picker currently allows PNG/JPG/WEBP and must be disabled for the MVP |
| Code languages | Python only | Gives the team a testable initial quality claim |
| Input text ceiling | Proposed: 200,000 extracted characters per request; tune after model-cost and latency spike | Prevents accidental unbounded context and cost; not yet a final implementation limit |
| Accounts | Required for saved server context in the current architecture | Existing frontend already exposes signup/login/session routes |
| Server retention | Delete uploaded or pasted content, extracted spans, and conversation content 24 hours after ingestion; allow earlier user deletion | Supports short follow-up use while limiting retained data |

File extension and MIME type alone are insufficient to validate uploads. The backend must inspect content, reject empty/corrupt files, and enforce size limits even if the browser has already checked them.

## Outside the first release

- OCR for scanned PDFs and image uploads.
- JavaScript/TypeScript or repository-wide code analysis.
- Executing uploaded code or applying AI-generated patches.
- Training or fine-tuning a foundation model.
- Multi-user shared workspaces, cross-device history, export, and vector search unless evaluation demonstrates a need.

## Release criteria

The team will test on a held-out set, with two human reviewers for answer quality:

| Measure | Target | Evidence |
|---|---:|---|
| Supported happy-path upload/chat cases | 100% pass | API and browser integration tests |
| Factual claims supported by source spans | At least 85% | 30 varied document cases, reviewer rubric |
| References resolve to stored source spans | At least 95% | Automated citation check |
| Flagged Python issues judged actionable | At least 75% | 30 varied Python cases, reviewer rubric |
| User-code execution paths | Zero | Design review and adversarial tests |
| Ordinary request completion without server error | At least 95% | 100-request staging run |

These are proposed gates and do not describe current performance. Any exception must be measured, documented, and agreed before release.

## Privacy and security decisions to record

- **Decided:** strict ₹0 spend for AI inference and hosting. Use a locally run model and localhost deployment on the team laptop.
- **Decided:** 24-hour server retention for uploaded content and extracted context, followed by automatic purge. The owning user can delete earlier.
- No raw upload content or passwords in application logs. Record request IDs, timings, model usage, and error classes instead.
- Model credentials remain server-side. Use HTTPS and secure HttpOnly cookies in deployment.
- Do not use private or copyrighted documents in the evaluation set without permission; prefer public-domain, self-authored, or openly licensed samples.
