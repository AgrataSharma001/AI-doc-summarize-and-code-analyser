/* Expected backend contract (same origin):
 * POST /api/documents/summarize: multipart file, summary_length, summary_style
 * POST /api/text/summarize: JSON text, summary_length, summary_style
 * POST /api/code/analyze: JSON code, explanation_level, expected_behavior
 * Responses: JSON objects; supported result fields are documented in results.js.
 * The backend must independently enforce input limits and validate uploads.
 */
window.DocodeAPI = (() => {
  const TIMEOUT_MS = 180000;

  async function request(path, options, signal) {
    if (!/^https?:$/.test(window.location.protocol)) {
      throw new Error('To generate results, serve this frontend over HTTP with the Python backend. Opening index.html directly only previews the interface.');
    }
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (signal?.aborted) abort();
    signal?.addEventListener('abort', abort, { once: true });
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, TIMEOUT_MS);
    try {
      const response = await fetch(`/api${path}`, { ...options, signal: controller.signal });
      if (!response.ok) {
        if (response.status === 404 || response.status === 405) throw new Error('The analysis API is not available. Connect the Python backend with the /api routes described in frontend/js/api.js.');
        if (response.status === 413) throw new Error('The backend rejected the input size. Try a smaller file or shorter text.');
        if (response.status === 429) throw new Error('The service is busy. Wait a moment and try again.');
        if (response.status >= 500) throw new Error('The backend could not complete this request. Check that the AI service is running, then try again.');
        throw new Error(`The request could not be processed (HTTP ${response.status}). Check your input and try again.`);
      }
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('The server did not return JSON. Check that the Python API is connected at /api.');
      const data = await response.json();
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('The backend returned an unexpected result format.');
      return data;
    } catch (error) {
      if (timedOut) throw new Error('The request took longer than three minutes. Try a shorter input or check the backend.');
      if (error.name === 'AbortError') throw error;
      if (error instanceof TypeError) throw new Error('Could not connect to the backend. Check that the Python server is running and try again.');
      if (error instanceof SyntaxError) throw new Error('The backend returned invalid JSON. Check the backend response.');
      throw error;
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
    }
  }

  const json = (path, data, signal) => request(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  }, signal);

  return {
    summarize({ file, text, length, style }, signal) {
      if (!file) return json('/text/summarize', { text, summary_length: length, summary_style: style }, signal);
      const body = new FormData();
      body.append('file', file);
      body.append('summary_length', length);
      body.append('summary_style', style);
      return request('/documents/summarize', { method: 'POST', body }, signal);
    },
    analyze(data, signal) { return json('/code/analyze', data, signal); },
  };
})();
