/* Same-origin backend contracts: frontend/README.md.
 * Authentication uses HttpOnly session cookies, never locally stored tokens.
 */
window.DocodeAPI = (() => {
  async function request(path, options = {}, signal, timeout = 180000) {
    if (!/^https?:$/.test(location.protocol)) throw new Error('This is a frontend preview. Serve it with the Python backend over HTTP to use chat or accounts.');
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
    try {
      const response = await fetch(`/api${path}`, { ...options, credentials: 'same-origin', signal: controller.signal });
      if (!response.ok) {
        const messages = { 401: path === '/auth/login' ? 'The email or password was not accepted.' : 'Please log in to continue.', 403: 'This request is not permitted. Refresh the page and try again.', 404: 'The Python API is not connected yet. This frontend needs the backend routes listed in frontend/README.md.', 405: 'This server only serves the frontend. Connect the Python API to enable this action.', 409: 'An account with this email may already exist. Try logging in.', 413: 'The upload is too large for the backend.', 422: 'The backend could not accept this input. Check the files and fields, then try again.', 429: 'Too many requests. Wait a moment and try again.' };
        const error = new Error(messages[response.status] || 'The service could not complete this request. Check the backend and try again.');
        error.status = response.status; throw error;
      }
      if (response.status === 204) return {};
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The backend did not return JSON. Check the API configuration.');
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('The backend returned an invalid response.');
      return data;
    } catch (error) {
      if (timedOut) throw new Error('The request timed out. Try a shorter input or check the backend.');
      if (error instanceof TypeError) throw new Error('Could not reach the Python backend. Check your connection and server.');
      if (error instanceof SyntaxError) throw new Error('The backend returned invalid JSON.');
      throw error;
    } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
  }
  const json = (path, data) => request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }, undefined, 20000);
  return {
    chat({ mode, message, files, history, conversationId }, signal) {
      const body = new FormData();
      body.append('mode', mode); body.append('message', message); body.append('history', JSON.stringify(history)); body.append('conversation_id', conversationId);
      files.forEach((file) => body.append('files', file));
      return request('/chat', { method: 'POST', body }, signal);
    },
    session: () => request('/auth/session', {}, undefined, 10000),
    login: (data) => json('/auth/login', data), signup: (data) => json('/auth/signup', data), logout: () => json('/auth/logout', {}),
  };
})();
