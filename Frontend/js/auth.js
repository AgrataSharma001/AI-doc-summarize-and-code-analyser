(() => {
  const $ = (id) => document.getElementById(id);
  let signup = false, busy = false;
  $('auth-switch').addEventListener('click', () => {
    if (busy) return;
    signup = !signup;
    $('auth-title').textContent = signup ? 'Make room for clarity.' : 'Welcome back.';
    $('auth-subtitle').textContent = signup ? 'Create your account to get started.' : 'A clearer perspective is one conversation away.';
    $('name-field').hidden = !signup; $('name').required = signup;
    $('password').minLength = signup ? 8 : 1;
    $('password').autocomplete = signup ? 'new-password' : 'current-password';
    $('password').placeholder = signup ? 'At least 8 characters' : 'Enter your password';
    $('password').value = ''; $('password').type = 'password'; $('show-password').textContent = 'Show'; $('show-password').setAttribute('aria-label', 'Show password');
    $('auth-submit').textContent = signup ? 'Create account →' : 'Log in →';
    $('switch-copy').textContent = signup ? 'Already have an account?' : 'New around here?';
    $('auth-switch').textContent = signup ? 'Log in' : 'Create an account';
    $('auth-error').hidden = true; $(signup ? 'name' : 'email').focus();
  });
  $('show-password').addEventListener('click', () => {
    const showing = $('password').type === 'password'; $('password').type = showing ? 'text' : 'password';
    $('show-password').textContent = showing ? 'Hide' : 'Show'; $('show-password').setAttribute('aria-label', showing ? 'Hide password' : 'Show password');
  });
  $('auth-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (busy) return;
    if (signup && !$('name').value.trim()) { $('auth-error').textContent = 'Please enter your name.'; $('auth-error').hidden = false; return; }
    busy = true;
    const payload = { email: $('email').value.trim(), password: $('password').value };
    if (signup) payload.name = $('name').value.trim();
    $('auth-fields').disabled = true; $('auth-switch').disabled = true;
    $('auth-submit').textContent = signup ? 'Creating account…' : 'Logging in…'; $('auth-error').hidden = true;
    try {
      const result = await window.DocodeAPI[signup ? 'signup' : 'login'](payload);
      if (!result.user || typeof result.user.id !== 'string' || typeof result.user.email !== 'string') throw new Error('The backend did not return an authenticated user. Check the authentication API.');
      // Server sets the HttpOnly cookie. No password or token is persisted.
      location.assign('index.html');
    } catch (error) { $('auth-error').textContent = error.message; $('auth-error').hidden = false; }
    finally { payload.password = ''; $('password').value = ''; busy = false; $('auth-fields').disabled = false; $('auth-switch').disabled = false; $('auth-submit').textContent = signup ? 'Create account →' : 'Log in →'; }
  });
})();
