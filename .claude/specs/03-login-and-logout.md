# Spec: Login and Logout

## Overview
Login lets a registered user sign in to Spendly with their email and password through the existing `/login` page, and logout ends that session. This step turns the static login form into a working POST handler that looks up the user by email, verifies the password against the werkzeug hash stored in `users.password_hash`, and stores the user's identity in a Flask session. Logout clears that session and sends the user back to the public landing page. It exists at this stage of the roadmap because the profile page (Step 4) and the expense pages (Steps 7–9) all need to know who the current user is, and registration (Step 2) has already created the accounts that can now sign in. Session storage is introduced here for the first time, so this step also configures `app.secret_key`.

## Depends on
- **Step 1 — Database setup**: the `users` table, `get_db()` with `PRAGMA foreign_keys = ON`, and `init_db()` / `seed_db()` at startup.
- **Step 2 — Registration**: `get_user_by_email()` in `database/db.py` and the `create_user()` helper, which give users something to log in with. The demo user (`demo@spendly.com` / `demo123`) from `seed_db()` is also available for testing.

## Routes
- `GET /login` — renders the login form (already implemented; no change to behaviour) — public
- `POST /login` — validates the submitted email and password, checks the password hash, sets the session on success, and redirects to `/`; on failure re-renders `login.html` with an error and status 400 — public
- `GET /logout` — clears the session and redirects to `/` — logged-in (a logged-out visitor who hits it is also redirected to `/`, so no error page is needed)

## Database changes
No database changes. The `users` table already has `id`, `name`, `email`, and `password_hash`, which is everything login and session storage need. Verified against `database/db.py`: `get_user_by_email(email)` already exists and returns a row or `None`. No new helpers are required.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Change the form `action="/login"` to `action="{{ url_for('login') }}"` (CLAUDE.md forbids hardcoded URLs).
    - Re-populate the `email` input with the submitted value on error (`value="{{ email or '' }}"`). Never re-populate the password.
    - Keep the existing `{% if error %}` block; it already displays `error`.
  - `templates/base.html`
    - Navbar: when `session.user_id` is set, show a "Sign out" link to `url_for('logout')` in place of the "Sign in" and "Get started" links; otherwise keep the current links. This is the only visible signal that login worked, since the profile page is still a stub.

## Files to change
- `app.py`
  - Import `os` (for the secret key), `session` from Flask, and `check_password_hash` from `werkzeug.security`.
  - Set `app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")` directly after `app = Flask(__name__)`.
  - Add `POST` handling to the `/login` route (keep `GET` rendering the form), following the same shape as `/register`.
  - Replace the `/logout` stub body with session clearing and a redirect. This is the Step 3 route, so implementing it is in scope.
- `templates/login.html` — action URL and sticky email value as described above.
- `templates/base.html` — conditional navbar links as described above.

## Files to create
None.

## New dependencies
No new dependencies. `session` is part of Flask, and `check_password_hash` is part of `werkzeug.security`, which is already pinned in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs. Use `sqlite3` via `get_db()` only.
- Parameterised queries only: every SQL statement uses `?` placeholders; never f-strings or string concatenation in SQL. Login reuses `get_user_by_email()`, which already follows this rule.
- Passwords are checked with `check_password_hash(stored_hash, password)` from werkzeug. Never compare plain text, and never store or log the plain password.
- Validation (in the route, before the DB lookup):
  - `email` and `password` are required; strip whitespace from `email` and lowercase it before lookup (same normalisation as registration).
  - If the email is unknown **or** the password does not match, show the same generic error: "Invalid email or password." Do not reveal which one failed. Return status 400.
  - On any validation error, re-render `login.html` with `error` set and status code 400. Do not return raw strings.
- Session handling:
  - On success, call `session.clear()` and then set `session["user_id"]` and `session["user_name"]`. Do not store the password hash or email in the session.
  - `/logout` calls `session.clear()`, then redirects.
  - Do not add `flask-login` or any other auth package.
- Use `abort()` for HTTP-level errors, not bare `return "error string"`.
- Use `url_for()` for every internal link and redirect target (`redirect(url_for('landing'))`).
- Route functions do one thing: read the form, call validation, call DB helpers, set or clear the session, and return a redirect or a rendered template. DB logic lives in `database/db.py`.
- Use CSS variables — never hardcode hex values. Reuse the existing `.auth-*`, `.form-*`, `.btn-submit`, and `.nav-*` classes. If a new style is needed, put it in a page-specific stylesheet, not inline.
- All templates extend `base.html`.
- Do not add route protection decorators or a `login_required` helper in this step. Protecting `/profile` and `/expenses/*` belongs to their own steps.
- Do not implement any other stub route (`/profile`, `/expenses/*`) in this step.
- Keep the app on port 5001.

## Definition of done
- [ ] `python app.py` starts without errors on http://127.0.0.1:5001.
- [ ] `GET /login` returns 200 and the form's `action` attribute is `/login` (rendered from `url_for`, not hardcoded in the template).
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/`.
- [ ] After that login, the navbar shows "Sign out" and no longer shows "Sign in" or "Get started".
- [ ] Logging in with `DEMO@spendly.com` (uppercase) and the correct password also succeeds, because the email is lowercased.
- [ ] A wrong password shows "Invalid email or password.", returns HTTP 400, and the email field still contains the submitted value while the password field is empty.
- [ ] An email that is not registered shows the same "Invalid email or password." message and returns HTTP 400.
- [ ] A blank email or blank password shows a validation error and returns HTTP 400.
- [ ] After a successful login, visiting `/logout` redirects (302) to `/`, and the navbar shows "Sign in" and "Get started" again.
- [ ] Visiting `/logout` while logged out also redirects to `/` with no error.
- [ ] After logout, the session no longer contains `user_id` (the navbar check above is the visible proof).
- [ ] The password hash and the plain password do not appear in the session cookie or in any page's HTML.
- [ ] `GET /register`, `GET /`, and `POST /register` still behave as in Step 2 (no regression).
- [ ] `GET /profile`, `GET /expenses/add` still return their placeholder text (no regression).
- [ ] No SQL string in `app.py` (all DB access goes through `database/db.py`).
