# P3-03 bounded uploaded-Python Ruff checks

Implemented on 2026-10-22; verified with Ruff 0.16.10.

## Workflow

For code-mode requests, the agent runs fixed Ruff checks against the same caller-authorized source snapshot used by the AST tools. Source reconstruction and AST resource/line-mapping checks run first. Limited or unmappable sources skip Ruff with an explicit coverage warning.

The checker runs the application's Python interpreter with -I -B -m ruff, feeding UTF-8 source to standard input under a constant uploaded.py display name. It disables config discovery, caches, automatic fixes, and noqa suppression. Uploaded filenames are never command arguments or filesystem paths. The selected rule families are F (Pyflakes), B (Bugbear), and S (Bandit-derived security checks). No uploaded module is imported or executed, and no source file is created or modified.

Ruff runs in a worker thread while the existing request concurrency gate is held. Limits are three seconds per subprocess, a five-second shared check budget, five attempted files per conversation request, 200,000 characters per source, one MiB of captured stdout per process, and 100 findings per file/conversation request. Timeouts and output overflow kill and wait for the child process. A missing/failing checker, malformed JSON, skipped file, truncated result, or unmappable finding produces an explicit status/warning; the model explanation may still succeed. The five-second budget covers checker time with process/thread overhead in addition. It is not OS memory isolation. Request cancellation can leave the worker completing its bounded checks after the HTTP task ends.

The first five eligible positions in stored file order are considered; later files receive budget_exceeded status. This is a known limitation for conversations containing many files. Follow-up requests recompute checks from retained sources instead of trusting browser history.

## Results and persistence

Code API responses now include findings and analysis.checks. Each mapped finding contains tool, rule, severity, file ID/name, line, column, message, reasoning, and supporting source IDs. Findings are deterministically derived from Ruff output and labeled potential issues. Severity is a screening priority: selected execution/deserialization/shell/SQL rules are high, other security rules and selected correctness/default-argument rules are medium, and remaining rules are low. It is not a measured exploitability or certainty score.

Only stored spans covering a finding's line can support it. The response's sources/source_ids include those spans even when the model's evidence budget omitted that section. Model citation validation still uses only the excerpts supplied to the model.

The reply appends a readable Ruff section so the existing frontend displays findings and coverage warnings. Successful code requests also save a Result of kind analysis containing the structured findings/checks; it shares the conversation's ownership and expiry lifecycle and is excluded from model-turn history. No database migration is required. A failed model request persists no new conversation, sources, answer, or analysis result.

Model reasoning and Ruff findings remain separate: the model does not receive Ruff output or generate these structured findings. Schema-validated model findings and their own line/evidence checks are now implemented in [P3-04](MODEL_FINDINGS.md). An empty findings list is not a claim that the program is correct or secure. Unsupported project-wide/import-resolution analysis and finding precision require further evaluation.

## Verification

- Full backend/API/migration suite: 142 passed, with one existing upstream Starlette TestClient deprecation warning.
- Final targeted Ruff/API rerun after severity/reasoning refinements: 42 passed.
- Project Ruff lint checks passed on changed Python modules/tests.
- Seventeen added cases cover real F401/F821/B006/S307 checks, ignoring local config/noqa, no uploaded-code execution or source/cache writes, original line mapping, timeout/output termination, malformed/unavailable checker output, count/file/parser limits, persisted/recomputed findings, citations outside model-selected excerpts, graceful unavailable-checker replies, and rollback when the model fails.
- API model responses are mocked; the Ruff subprocess is real in happy-path tests. No live model-quality/latency/RAM benchmark or held-out finding-precision assessment was performed.

## Next task

Structured model findings and combined display are implemented in [P3-04](MODEL_FINDINGS.md). Continue with failure-stage telemetry/memory profiling and the pending demo-laptop model evaluation.
