# Architecture and project decision log

Record the date, owner, reason, and consequences for each decision. `Accepted` means the user confirmed the constraint or it follows directly from the current repository; technical choices marked `Proposed` still need team review.

| ID | Date | Status | Decision | Reason and consequence |
|---|---|---|---|---|
| ADR-001 | 2026-10-06 | Accepted | Incremental ₹0 spend for AI inference and hosting | Use local inference and existing hardware; no paid model API or managed hosting. |
| ADR-002 | 2026-10-06 | Accepted | Localhost demo is sufficient | Public URL and hosting region are out of scope for this release. Serve UI and API from one local origin. |
| ADR-003 | 2026-10-06 | Accepted | Server-held upload and conversation context expires after 24 hours | Add automatic purge and user-requested early deletion; expiry must include extracted spans and cached answers. |
| ADR-004 | 2026-10-06 | Accepted | Demo laptop has 8 GB RAM or less | Start model testing at Qwen3 1.7B; 4B only if the actual laptop can run it within memory and timeout limits. No model quality claim before measurement. |
| ADR-005 | 2026-10-06 | Proposed | Use SQLite for the first release | Eliminates a separate database service on the laptop. Enable foreign keys, define migrations, and test concurrent access assumptions. |
| ADR-006 | 2026-10-06 | Proposed | Use Ollama as local HTTP model server | Simple local adapter and model switch; benchmark on real laptop before accepting. Bind API to loopback. |
| ADR-007 | 2026-10-06 | Proposed | Require login for server-held chat context | Matches existing auth UI and simplifies ownership. The frontend must gate guest chat or explain 401. |
| ADR-008 | 2026-10-06 | Proposed | Use deterministic agent orchestration, no uploaded-code execution | Easier to review and measure; limits untrusted source text to evidence rather than instructions. |

## Open decisions

- Assign actual student names to A, B, C, and D.
- Record exact laptop CPU, RAM, GPU/VRAM, and free disk space before the model spike.
- Select Qwen3 1.7B or 4B only after the [measured spike](MODEL_SPIKE.md). If neither meets the gate, narrow claims and document limitations.
- Decide whether the production-ready path later requires HTTPS/public hosting; the current release is localhost only.
