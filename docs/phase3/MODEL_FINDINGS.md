# P3-04 structured model review findings

Implemented on 2026-10-22.

## Schema and validation

Document responses retain the existing reply/source_ids schema. Code responses now require findings, an array of at most eight entries (an empty array is valid). Each model finding has severity (low/medium/high), source_id, inclusive start_line/end_line, message, and reasoning. Unknown fields, invalid types, missing fields, unsupported severities, blank prose, fabricated citation markers, duplicate findings, reversed ranges, and source/line references outside supplied evidence are rejected.

A finding must fit within the line range of one actual supplied code excerpt. Being in the same conversation is insufficient: a stored but unselected source cannot support a model finding. Multi-excerpt ranges must be narrowed to a supported excerpt. File ID/name are derived from stored evidence, never accepted from the model. Finding source IDs are added to the answer citation set even when the model's general reply cites a different excerpt.

Validation is shared between the Ollama adapter and the agent boundary, so replacement adapters cannot bypass it. Invalid output receives the existing single bounded retry inside the adapter; a second invalid response returns 502 and saves no new sources, answer, or analysis. Code generation permits up to 1,024 output tokens (documents retain 512); existing request deadlines still apply.

## Display and storage

The code API findings array now combines model and Ruff findings. Each carries tool=model or tool=ruff to preserve provenance. Model entries include a server-derived filename/file ID, line/end_line, severity, message, reasoning, and source_ids; rule and column are null because they are not checker diagnostics. Existing Ruff entries retain their rule and column. Findings from the two providers are kept distinct rather than semantically deduplicated.

Both use shared readable formatting and appear in the existing frontend reply. Code-review requests use a neutral server-written summary followed by structured potential issues; free-form model review prose is not displayed. Explanation requests retain the model's explanatory prose. Successful analysis results store both providers' structured findings, using the same ownership, history exclusion, and retention behavior as P3-03. The API also reports analysis.model_review with validation status and finding count. No database migration is needed.

Prompts request source-visible failure mechanisms, avoid undocumented input-contract assumptions, and reserve high severity for supported security/data-loss risks. These instructions do not establish semantic accuracy. The validator checks schema and source bounds, not whether a claimed defect is real or whether severity is justified.

## Verification

- Full backend/API/migration suite: 163 passed; one existing upstream Starlette TestClient deprecation warning.
- Final focused finding/agent checks after prompt refinement: 35 passed. API reply checks were rerun after the neutral-summary display change.
- Ruff lint passed for changed implementation/test files.
- Twenty-one added cases cover strict schema rules, unsupported/omitted source IDs, out-of-range/reversed lines, duplicates and limits, unknown file metadata, bounded retry/recovery, replacement-adapter rejection, cross-source citation union, server-derived provenance, combined model/Ruff display and persistence, retained follow-up references, and rollback after invalid model output.

### Live local model check

Synthetic input used with local Ollama qwen3:1.7b:

    def mean(values):
        return sum(values) / len(values)

After the final prompt refinement, the actual agent/adapter returned a schema-valid review in 5,192 ms and explanation in 2,163 ms. The review included a medium-severity conditional division-by-zero finding at line 2; the explanation returned an empty findings array. Ruff checks completed successfully. This exercised the real model and checker through the agent, without database/browser persistence; authenticated persistence/display are covered by mocked-model API tests.

Initial live attempts timed out at 45 and 60 seconds. Later attempts completed, but this does not establish response reliability. Raw live review prose also contained incorrect/contradictory claims and did not consistently follow the requested neutral summary. The code-review endpoint therefore displays its own neutral summary and renders the validated structured findings. Model reasoning and severity still require held-out human evaluation. No factual-accuracy, precision, latency-percentile, or memory release gate has been established.

## Next work

Complete failure-stage/validation telemetry and memory-pressure profiling. Run the demo-laptop quality/latency/RAM evaluation and tune the model/prompts against the development set before assessing held-out release gates. Long-document chunk synthesis remains separate future work.
