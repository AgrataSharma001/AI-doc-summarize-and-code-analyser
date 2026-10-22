# P3-02 read-only source tools and Python structure

Implemented on 2026-10-22.

## Behavior

backend/source_tools.py creates a snapshot of files already authorized by the chat endpoint. get_source_span accepts only span IDs in that snapshot; list_sections returns stored span locations for a scoped file; get_python_symbols returns a cached structural analysis for a scoped file. Unknown IDs raise KeyError. Returned data is copied so callers cannot mutate the snapshot or cached analysis. These are controller tools, not public HTTP endpoints or model-selected function calls.

backend/python_analysis.py tokenizes and parses Python without importing or executing it. It identifies classes, functions, async functions, nested qualified names, decorator-inclusive start lines, definition lines, and end lines. Syntax/tokenization failures produce structured diagnostics rather than rejecting an otherwise valid text upload. Symbols omit signatures, type inference, call graphs, and semantic bug detection.

Code-mode preparation reconstructs the full stored file in span order, restoring skipped blank-line gaps from source locations. CRLF/CR are normalized for parsing. Nonstandard line separators and non-Python location formats produce an explicit unavailable-analysis warning rather than guessed line numbers. Content of discarded whitespace-only chunks cannot be recovered exactly; reconstruction preserves their line gaps for structural inspection.

Only symbols overlapping selected excerpts are attached as python_analysis metadata. At most 20 symbols are attached per excerpt; excess symbols are disclosed. JSON metadata counts against the existing evidence character budget. When necessary, selection trims symbols or omits metadata to retain source text and adds a coverage warning. Source IDs and stored reference locations stay unchanged. Metadata is recomputed from retained spans on follow-up; no database migration is needed. Document-mode evidence remains unchanged.

Limits: 200,000 input characters per file, 50,000 tokens, 80 bracket nesting levels, 50,000 visited AST nodes, and 1,000 symbols. Parser recursion/memory errors are reported as analysis limits. These are application limits, not OS process isolation or a measured CPU/RAM guarantee. Python syntax support follows the installed interpreter.

## Verification

- Full backend/API/migration suite: 125 passed; one existing upstream Starlette TestClient deprecation warning.
- Ruff lint passed for changed implementation and test files. This checks the project code; uploaded-code Ruff analysis is still pending.
- Thirteen added regression cases cover decorated/nested/async Unicode symbols, CRLF lines, malformed source, character/nesting limits, long split lines and skipped blank chunks, scoped IDs and copy isolation, non-execution, evidence budgets, unusual line mappings, and authenticated Python upload/follow-up with stable citations.
- API model responses are mocked. No live Ollama quality, Python finding-precision, or hardware benchmark was run.

## Next work

Bounded Ruff checks and structured tool findings are now implemented in [P3-03](RUFF_CHECKS.md). Schema-validated model-generated findings are implemented in [P3-04](MODEL_FINDINGS.md); continue with telemetry/memory profiling and live quality evaluation. The demo-laptop model-quality/latency/RAM spike remains pending independently.
