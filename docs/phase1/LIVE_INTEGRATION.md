# P1-05: live integration evidence

Verified on 2026-10-11 using the real browser, API, database, and local model. No API or model responses were mocked in the live test.

## Environment

- Windows, headless Microsoft Edge through Playwright.
- FastAPI served the frontend and API from `http://127.0.0.1:8765`.
- Ollama at `http://127.0.0.1:11434`, model `qwen3:1.7b`.
- Installed model digest: `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7` (reported by Ollama `/api/tags`).
- This run used the existing local development database and synthetic input only. Future runs should use the dedicated test database in the [browser verification instructions](../../Frontend/README.md#browser-verification).

## Results

| Check | Result |
|---|---|
| Backend/API/migration suite | 56 passed; one upstream Starlette TestClient deprecation warning |
| Existing mocked frontend smoke test | All four groups passed, including mobile layout and safe output |
| Signup | Real account and HttpOnly session cookie created; password absent from browser storage |
| TXT upload and answer | Project budget and owner matched the synthetic source; displayed citations matched API source metadata |
| Initial answer elapsed time | 9,589 ms, measured from browser send through reply display |
| Follow-up after page reload | Same conversation and stored file; budget matched; multipart request contained no uploaded file |
| Follow-up elapsed time | 2,242 ms, measured from browser send through reply display |
| Logout | Session endpoint returned `user: null`; subsequent chat request returned 401 |
| Browser JavaScript errors | None |

The fixture contains a three-line Project Orion note with a 240-rupee budget, a deadline, and an owner. The test checks the budget and owner on the first answer and the budget on the follow-up. This verifies the supported TXT vertical slice and retained-source behavior. Timings are two individual requests, not a performance benchmark. Factual quality across the evaluation corpus, deadline accuracy, peak RAM, Python analysis quality, and the 20-case model comparison remain unmeasured by this test.

## Next work

P1-05 is complete for the current TXT workflow. Proceed to P2-01: PDF/DOCX extraction and page/section mapping. The Phase 0 hardware/model spike and reviewer evaluation remain separate pending work.
