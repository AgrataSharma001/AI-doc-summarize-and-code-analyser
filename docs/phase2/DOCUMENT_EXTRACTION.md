# P2-01 document extraction

PDF and DOCX uploads now use the existing authenticated chat workflow, server-held source spans, citation validation, and 24-hour conversation retention. No uploaded code or document macros are executed.

## Source mapping and coverage

- PDF text is extracted page by page and chunked into bounded spans with `page N, lines A-B` locations. Page numbers refer to the original PDF; lines refer to the extracted page text. A textless page is skipped with a coverage warning; a file with no extractable text returns an OCR-related error.
- DOCX body paragraphs and tables are traversed in document order, including nested tables within configured limits. References identify heading sections, paragraph numbers, table rows, and cells. Merged cells are not repeated. DOCX references do not assert rendered page numbers.
- DOCX images, text boxes, headers/footers, and tracked changes may be omitted. Every DOCX answer from a new upload discloses that coverage limit. Extraction warnings are included in the initial reply, not stored as separate file metadata.
- Each accepted span receives a unique ID once, and the same stored ID/location is used on follow-up. IDs are not recomputed from a fresh extraction.
- Extractors commit their spans only after successful extraction. A failed multi-file request calls no model and persists no new sources.

## Limits and errors

The existing five-file, 10 MiB combined upload limit, 200,000 extracted characters per source, and 500,000 characters per conversation still apply. PDFs also have a 200-page cap, 4 MiB decoded content per page, and 20 MiB decoded page content overall. pypdf decompression, page-tree, and form traversal limits are applied in the extraction context. DOCX packages are limited to 1,000 entries and 20 MiB expanded data, reject duplicate names/encryption and XML DTD/entity declarations, and bound visited blocks, nested tables, and location length. These are parser limits, not an OS-enforced CPU/memory sandbox.

Malformed, encrypted, and textless documents return actionable 422 errors. Resource limits return 413. MIME/extension mismatches remain 415. PDF layout reconstruction, OCR, charts, and general semantic reading-order accuracy are outside this task. A scanned page with an existing OCR text layer is treated as text; extraction does not assess that layer's correctness.

## Verification on 2026-10-11

- Backend/API/migration suite: 76 passed, including 20 document tests. One upstream Starlette TestClient deprecation warning remains.
- Ruff checks passed for changed backend modules and document tests/fixtures.
- Existing frontend smoke test passed, including PDF/DOCX picker acceptance and rejection in Python mode.
- Real headless Edge -> FastAPI -> Ollama `qwen3:1.7b` tests passed for both PDF and DOCX. Each test verified signup, source-grounded answer with displayed locations, budget/owner facts, follow-up after reload without another upload, logout, and signed-out rejection. No API/model responses were mocked in these runs.
- PDF initial answer: 14,740 ms; follow-up: 4,168 ms. DOCX initial answer: 4,104 ms; follow-up: 4,435 ms. These are individual browser request/display timings, not a benchmark.
- Live tests used synthetic fixtures and a dedicated ignored `data/extraction-test.db`. No browser JavaScript errors were observed. Synthetic accounts remain in that database; conversation content expires under the normal retention policy.

Setup and fixture generation are documented in [browser verification](../../Frontend/README.md#browser-verification). Tests cover corrupt/empty/encrypted PDFs, absent text, expanded streams, character/page/archive limits, unsafe DOCX XML, merged cells, source order, citations, retained follow-ups, and atomic failure.

## Next work

Continue Phase 2 with TXT/Markdown paragraph/heading boundaries and a broader retrieval evaluation corpus. P2-01 does not complete the remaining Phase 2 checklist or the Phase 0 model-quality/RAM spike.
