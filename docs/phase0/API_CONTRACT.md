# Phase 0, task 2: frontend-to-backend API contract

**Status:** Proposed contract mapped from `Frontend/README.md` and `Frontend/js/api.js` on 2026-10-06. Authentication is required for chat in this MVP. The frontend must gate guest chat or explain the 401 response. Localhost is the agreed demo target.

## Transport and common rules

- Same-origin HTTP on localhost for the ₹0 demo; JSON responses except `204 No Content`. If later exposed publicly, require HTTPS.
- Session credential is a server-set `HttpOnly`, `SameSite` cookie. Set `Secure` under HTTPS; local HTTP cannot use an HTTPS-only cookie. No bearer token or model credential in browser storage.
- Mutating endpoints require an Origin check and CSRF protection appropriate to the chosen cookie policy. Rate-limit signup, login, and chat.
- Error response shape for new backend code: `{"error":{"code":"VALIDATION_ERROR","message":"...","request_id":"..."}}`. The current frontend uses HTTP status-based messages; it can later display safe backend messages.
- Server validates all content independently of client controls. Browser `history`, `conversation_id`, filenames, and MIME headers are untrusted. Store conversation ownership by authenticated user ID.

## Authentication routes

| Route | Request | Success response | Common errors |
|---|---|---|---|
| `GET /api/auth/session` | Cookie if present | `200 {"user":null}` or `200 {"user":{"id":"...","name":"...","email":"..."}}` | `500` |
| `POST /api/auth/signup` | JSON `{"name":"...","email":"...","password":"..."}` | `200 {"user":{...}}` and session cookie | `400/422`, `409`, `429` |
| `POST /api/auth/login` | JSON `{"email":"...","password":"..."}` | `200 {"user":{...}}` and session cookie | `401`, `429` |
| `POST /api/auth/logout` | Session cookie | `204`, invalidate server session and cookie | `403` if Origin/CSRF fails |

Never echo a password or password hash. Use generic invalid-login text so the API does not disclose whether an email is registered. An unauthenticated `GET /api/auth/session` returns `user: null` rather than an error because that is the frontend's current expectation.

## Chat route

**Current implementation:** Intake is implemented and returns `200` with `status: intake_accepted`, `conversation_id`, file metadata, and a `reply` explaining that AI answering is pending. This is a validation acknowledgement, not the final answer contract below. File contents, pasted content, and browser history are not retained in this step. Reattach source content when extraction/model answering becomes available. Conversations are owner-bound, mode-bound, and expire after 24 hours; expired conversations are removed when their owner next accesses them. Text uploads require UTF-8. Additional transport limits are 12 MiB per multipart body, 256 KiB for history, 200 history messages, and 20 chat attempts per user per minute.

`POST /api/chat` with `multipart/form-data`:

| Field | Type | Rule |
|---|---|---|
| `mode` | Text | Exactly `document` or `code` |
| `message` | Text | Instruction, question, or pasted content; current UI caps at 200,000 characters; server must also cap it |
| `conversation_id` | Text | Client-generated ID; first request binds it to the authenticated user; subsequent requests must match that owner |
| `history` | JSON text | Array of `{role,content,attachments}` for display continuity only; not authoritative for source access or previous model turns |
| `files` | Repeated file field | Zero to five files, at most 10 MiB combined; at least a nonblank message or one file is required |

MVP server extensions: `.txt`, `.md`, `.pdf`, `.docx` in `document` mode and `.py` in `code` mode. For first release, reject mixed document/code attachments and unsupported image types. Check actual content, not extension alone. Uploaded or pasted content, extracted spans, and source locations stay server-side for follow-up requests and are purged 24 hours after ingestion. A fresh request with no file can use previously stored context only for the same user and conversation.

**Minimal success response compatible with the frontend:**

```json
{
  "reply": "The report's main finding is ... [source: file-1, page 2]"
}
```

The frontend also accepts `summary`, `explanation`, `purpose`, `key_points`, `findings`, `suggestions`, `tests`, `warnings`, `source_ids`, and `revised_code`, but currently flattens them into plain text. For the vertical slice, return `reply`; define a richer, versioned response only when citation UI is implemented. References in `reply` must resolve to server-stored source IDs and locations.

| Status | Meaning | Expected client handling |
|---:|---|---|
| `200` | Valid answer | Render reply as text |
| `401` | No active session | Open/login prompt; preserve draft |
| `403` | Conversation belongs to another user or CSRF failure | Do not reveal source content |
| `404` or `410` | Referenced context unavailable/expired | Ask user to reattach content |
| `413` | Request/file limit exceeded | Explain size/count limit |
| `415` or `422` | Unsupported, corrupt, empty, or unextractable content | Explain the specific safe error |
| `429` | Rate limit or local model capacity limit | Show retry guidance |
| `502/503/504` | Model provider unavailable or timeout | Preserve draft and allow retry |

Browser cancellation aborts the request, but server work may already have started. Add server timeouts and cancellation handling; do not claim that stopping the browser always stops provider billing.

## Data deletion route to add during integration

`DELETE /api/conversations/{conversation_id}` uses the session cookie and CSRF protection. The server confirms ownership, deletes conversation messages/results and extracted source spans/files, and returns `204`. Return `404` for an unknown or unauthorized-to-disclose ID. The current frontend only deletes its tab-local history; the UI must call this route to promise server deletion.

## Contract checks before Phase 1 exit

1. Signup/login/session/logout work with the current frontend and real cookies.
2. `POST /api/chat` receives multipart fields exactly as sent by `Frontend/js/api.js`.
3. A second user cannot read, continue, or delete the first user's conversation.
4. Invalid type/size, expired context, and provider failure yield controlled status codes and no internal tracebacks to the browser.
5. The frontend aligns its picker with the server: add `.md`; disable image types until OCR/vision exists; gate chat for guests.
