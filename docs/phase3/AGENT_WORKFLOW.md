# P3-01 bounded agent workflow

Implemented on 2026-10-22.

## Control flow

The authenticated chat endpoint delegates to backend/agent.py:

1. Classify the explicit UI mode and request into document_summary, document_qa, code_explanation, or code_review.
2. Select bounded evidence from caller-authorized source files using the existing selector. Reject empty evidence before calling the model.
3. Call the replaceable model adapter with the selected route and retained server-side turns.
4. Validate the provider-independent answer schema.
5. Validate that citations are unique IDs from the selected evidence and that prose contains no fabricated source markers.
6. Return the validated result for the endpoint to persist and format with stored locations.

The adapter adds a route-specific instruction, retains its maximum of two HTTP attempts for malformed output, and uses shared validation in backend/answers.py. The controller performs no additional retries. The existing overall deadline, single-model concurrency gate, ownership/expiry rechecks, and save-only-on-success behavior remain in the endpoint. The controller exposes no shell, file-write, network-browsing, or uploaded-code execution tools.

Routing is a deterministic keyword heuristic over the request, not a trained intent classifier. Source text and retained turns cannot select a route. Ambiguous requests can therefore use a less suitable prompt. Code review now receives AST/tokenize structure and syntax diagnostics through [P3-02](PYTHON_TOOLS.md). Ruff checks and structured tool findings are now implemented in [P3-03](RUFF_CHECKS.md) and displayed separately from model prose. Structured model findings are implemented in [P3-04](MODEL_FINDINGS.md). Long-document chunk synthesis remains future work. Citations establish resolvable evidence references, not factual support for every claim.

Completed chat logs now include the route and ordered stages alongside existing timing/token counts, without adding raw source text. Failure-stage telemetry and memory profiling remain pending.

## Verification

- Full backend/API/migration suite: 112 passed, with one existing upstream Starlette TestClient deprecation warning.
- Sixteen new cases cover four routes, source-instruction separation for routing, empty/invalid intake, recovery after one invalid provider attempt, and rejection of malformed answers from replacement adapters.
- Ruff checks passed for all changed Python files.
- Provider calls in these tests are mocked. No live Ollama quality or hardware benchmark was run for this change.

## Next work

Read-only source/Python-symbol tools and Python AST/tokenize analysis are implemented in [P3-02](PYTHON_TOOLS.md). Bounded Ruff static checks are now implemented in [P3-03](RUFF_CHECKS.md); structured model review findings are implemented in [P3-04](MODEL_FINDINGS.md). Continue with telemetry/memory profiling and model-quality evaluation. Keep uploads non-executable. The Phase 0 model-quality/latency/RAM spike remains pending.
