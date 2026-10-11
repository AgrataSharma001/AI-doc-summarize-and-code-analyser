# Docode frontend

HTML, CSS, and vanilla JavaScript chat interface. Open `index.html` to preview the workspace or `login.html` for login/signup. No build step or third-party frontend dependencies are required.

Theme preference is stored locally; chat history is stored in the current tab's session storage, separated by server-provided user ID. File bytes and passwords are not saved in browser storage. Browser history storage is a convenience, not an authorization boundary.

## Backend integration

Serve this directory and the API from the same origin. This frontend does not implement an AI service or authentication server and does not offer fake credentials. The root Python dependency files concern the planned backend; this interface needs no Python packages.

### Chat

`POST /api/chat` accepts multipart form data:

- `mode`: `document` or `code`.
- `message`: instructions, question, or pasted content.
- `conversation_id`: client-generated conversation ID; the server must enforce ownership.
- `history`: JSON array of previous `{role, content, attachments}` messages. Attachment entries contain metadata only.
- `files`: repeated upload fields. The UI allows 5 files totaling at most 10 MiB: TXT/Markdown in document mode and Python in code mode. PDF/DOCX and images are disabled until extraction/OCR support exists. The server separately caps each extracted text source at 200,000 characters and a conversation's sources at 500,000 characters.

Return `{"reply":"Your answer..."}`. Structured responses with `summary`, `explanation`, `purpose`, `key_points`, `findings`, `suggestions`, `tests`, `warnings`, `source_ids`, and `revised_code` are also accepted. Responses are rendered as plain text; generated HTML never executes.

The backend retains text spans and successful turns by conversation ID for follow-up questions: prior file contents are not resent. The first message without files is treated as pasted source; later messages ask questions about stored sources. To add a pasted source later, prefix it with `Source:` followed by a newline. Replies include validated span IDs and line references as plain text. Context access expires after 24 hours; the UI displays the backend's expiry and model errors. The backend uses local Ollama, which must be installed and running separately. The frontend does not execute code. Cancellation aborts the browser request, not necessarily server-side work. Chat requests time out after 180 seconds. Failed requests keep the draft and files for retry.

### Authentication

- `GET /api/auth/session` returns `{"user":null}` for guests or `{"user":{"id":"user-id","name":"Alex","email":"alex@example.com"}}`.
- `POST /api/auth/login` accepts JSON `{email,password}`, returns the user object above, and sets an HttpOnly session cookie.
- `POST /api/auth/signup` accepts JSON `{name,email,password}`, returns the same authenticated user/session. If verification is required, adapt the frontend for that flow before enabling signup.
- `POST /api/auth/logout` returns 204 or a JSON object and invalidates the session cookie server-side.

Implement server-side password hashing, validation, rate limits, secure HttpOnly cookies in HTTPS deployments, and CSRF protection (including appropriate SameSite and Origin checks). Enforce ownership on authenticated operations. The frontend never stores a password or bearer token. Signup has an 8-character minimum as basic client validation; the backend owns password policy.

Switch accounts calls logout, clears the current account's browser chat history, and opens login. If logout fails, the interface does not claim the session ended.

## Interaction

- Sidebar: new chat, explore templates, document/code modes, recent conversations, account menu.
- Composer: plus menu or drag/drop attachments, instructions, and send. Desktop Enter sends; Shift+Enter and mobile Enter insert a newline.
- Appearance: light, dark, or system in Settings; quick light/dark toggle in the account menu.
- History: at most 30 recent chats with confirmed deletion in Settings. Storage availability and capacity depend on the browser.
- Login: email/password, password visibility, signup, account switching, and backend error feedback.

Recent chats are local to this browser session and not synchronized across devices. Clearing browser history does not yet call a server deletion endpoint; server sources/results expire after 24 hours and are purged on startup/every minute. No simulated AI answers are generated when the backend or model is unavailable.

## Browser verification

`tests/smoke.cjs` checks UI behavior with mocked API responses. `tests/live.cjs` uses the real frontend, FastAPI, SQLite, and Ollama without intercepting requests. The live test creates a synthetic account and conversation, uploads a TXT file, checks displayed citations and simple source facts, reloads the page, asks a follow-up without reuploading, and verifies logout and signed-out rejection. It does not measure general model quality or peak RAM.

Install browser test dependencies from the repository root (the local directory is ignored by Git):

```powershell
npm install --prefix .test-tools --no-package-lock --no-save playwright
```

Start Ollama with the configured model installed. In a separate terminal, start the backend against a dedicated test database:

```powershell
$env:DOCODE_DATABASE_URL = 'sqlite:///data/live-test.db'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
```

Run both tests from the repository root:

```powershell
$env:PLAYWRIGHT_MODULE = (Resolve-Path '.test-tools/node_modules/playwright').Path
$env:BROWSER_CHANNEL = 'msedge'
$env:DOCODE_TEST_URL = 'http://127.0.0.1:8765'
node Frontend/tests/smoke.cjs
node Frontend/tests/live.cjs
```

This example uses installed Microsoft Edge. Alternatively, install Playwright Chromium with `.\.test-tools\node_modules\.bin\playwright.cmd install chromium` and remove `BROWSER_CHANNEL` from the environment. The live test accepts only a loopback HTTP URL and fails if the API/model is unavailable. Each run adds a synthetic user; conversation sources expire after 24 hours, while accounts remain in the test database. Stop the backend before removing that dedicated database. See [P1-05 evidence](../docs/phase1/LIVE_INTEGRATION.md) for the recorded run.
