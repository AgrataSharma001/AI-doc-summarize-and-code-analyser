# P2-02 text structure and retrieval

Completed on 2026-10-13.

## Extraction

TXT uploads split at blank-line paragraph boundaries before applying the 1,600-character span limit. Markdown uploads and pasted document text additionally recognize ATX and Setext headings and carry the latest section title into subsequent paragraph locations. Headings inside backtick/tilde fences remain literal content. This is a lightweight boundary recognizer, not a full CommonMark parser; lists, block quotes, and nested Markdown structures have no dedicated parser.

Locations retain original line numbers, including CRLF inputs. Long paragraphs/lines split into bounded spans; a boundary-aligned trailing line ending stays attached to text. Section labels are capped at 60 characters to fit the existing 100-character location field. Original heading content remains in the source. Python inputs retain line-only extraction; PDF page and DOCX paragraph/table mapping remain in their existing extractors. Stored IDs/locations are reused on follow-up; previously stored conversations are not rechunked.

## Evidence selection and evaluation

Keyword overlap now considers location labels as well as content, allowing an answer paragraph to match a heading inherited from an earlier chunk. Ties retain source order. Evidence stays within the existing character budget; partial-coverage warnings remain in place.

The deterministic synthetic retrieval set in `tests/test_sources.py` has 11 known-answer cases:

| Cases | Check |
|---|---|
| 6 | Early, middle, and late answer paragraphs in 20-paragraph TXT/Markdown inputs |
| 1 | Answer paragraph matched through an inherited Markdown heading |
| 1 | Relevant evidence from two files, in source order and within budget |
| 1 | Unicode/case matching, plus full-coverage behavior with a larger budget |
| 2 | Answer on PDF page 15 and in a DOCX heading section, with original locations |

All 11 pass. Each checks the expected answer content; location/ID, budget, coverage, and source-order assertions cover the relevant cases. A too-small budget returns no evidence rather than exceeding the limit. These are small, self-authored regression cases, not held-out semantic retrieval or model factual-quality measurements. Keyword retrieval still misses synonyms and ambiguous follow-ups. Long-document summaries still use selected excerpts; chunk-by-chunk synthesis remains future agent work.

## Verification

- Full backend/API/migration suite: 96 passed; one existing upstream Starlette TestClient deprecation warning.
- Added 20 tests: 7 extraction checks, 11 retrieval cases, and 2 authenticated upload/follow-up tests covering TXT and Markdown citation persistence.
- Ruff checks passed for changed backend modules and tests.
- Model responses in API checks are mocked. No new live browser/model benchmark was run.

## Next task

Begin Phase 3 with an explicit bounded agent state machine, reusing existing extraction, evidence selection, model adapter, and citation validation. The Phase 0 demo-laptop model-quality/latency/RAM spike remains pending.
