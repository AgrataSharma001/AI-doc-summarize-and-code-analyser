# Evaluation set and scoring method

These 80 short, self-authored cases are the initial **semantic evaluation set**. Each JSONL line has an ID, `split`, source content, a question, and expected answer elements. `documents.jsonl` has 40 document cases; `python_code.jsonl` has 40 Python cases. Ten from each file are assigned to the model-selection spike and 30 from each are held out to reduce tuning on the final evaluation. The cases contain no private user data.

This corpus tests answer grounding and code reasoning. It does **not** test PDF/DOCX extraction, large-file chunking, or browser uploads. Those need separate physical fixtures and integration tests in later phases. Do not present these short cases as proof of long-document performance.

## Document scoring

For each held-out case, two reviewers independently identify factual claims in the answer and compare them with the source. Mark each claim `supported`, `unsupported`, or `not verifiable from source`. Report factual support as supported claims divided by all factual claims, with numerator and denominator shown. Record omitted required facts from the `expected` field separately. A response that simply refuses every case must not pass through high factual precision alone.

If the agent emits source IDs/page/section references, validate each against the stored source map. Citation validity is valid references divided by emitted references. Cases with no emitted references fail the citation-presence requirement where a reference is available; do not make the denominator zero and claim success.

## Python scoring

Review each distinct issue flagged by the analyzer. Mark it `actionable`, `incorrect`, or `uncertain`; report precision as actionable findings divided by all flagged findings. Also mark whether the expected behavior/edge case in the JSONL record was covered. Two reviewers resolve disagreements before the final score. Do not execute uploaded code in the application; reviewers can reason from source or use separate trusted test harnesses for self-authored examples.

## Result sheet columns

Keep a CSV with `case_id`, `model_digest`, `prompt_version`, `reviewer`, `facts_supported`, `facts_total`, `expected_covered`, `citations_valid`, `citations_total`, `findings_actionable`, `findings_total`, `latency_seconds`, `error`, and `notes`. Store individual reviewer rows and a resolved row. Report sample size, error count, median/p95 latency, and any known failure clusters.

## Release gates

- At least 85% document factual support on the 30 held-out document cases, with coverage of expected points reported alongside it.
- At least 95% valid references when references are emitted, and references present where source mapping supports them.
- At least 75% actionable Python findings on the 30 held-out code cases, with expected behavior coverage reported alongside it.
- No uploaded-code execution path and no cross-user source disclosure.

The 30-case-per-category held-out target from the project plan is now met for short semantic cases. Add separate real PDF/DOCX and long-document fixtures before claiming extraction or long-context quality.
