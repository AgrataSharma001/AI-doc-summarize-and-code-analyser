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
- `files`: repeated upload fields. The UI allows 5 files totaling at most 10 MiB: PDF, DOCX, TXT, PY, PNG, JPG, JPEG, WEBP. Server-side validation is mandatory.

Return `{"reply":"Your answer..."}`. Structured responses with `summary`, `explanation`, `purpose`, `key_points`, `findings`, `suggestions`, `tests`, `warnings`, `source_ids`, and `revised_code` are also accepted. Responses are rendered as plain text; generated HTML never executes.

The backend must retain extracted document/image context by conversation ID for follow-up questions: prior file contents are not resent. Explain expired context and ask for reattachment. Photos require backend OCR or a vision model. The frontend does not execute code. Cancellation aborts the browser request, not necessarily server-side work. Chat requests time out after 180 seconds. Failed requests keep the draft and files for retry.

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

Recent chats are local to this browser session and not synchronized across devices. No simulated AI answers are generated when the backend is unavailable.
