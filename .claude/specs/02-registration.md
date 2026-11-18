# Spec: Registration

## Overview
Registration lets a new visitor create a Spendly account by submitting their name, email, and password through the existing `/register` page. This is the first step that writes user data: it turns the static register form into a working POST handler that validates input, hashes the password with werkzeug, and inserts a row into the `users` table created in Step 1. It exists at this stage of the roadmap because login (Step 3 flow) and the profile and expense pages all depend on having real users in the database. Session handling is out of scope here; after a successful signup the user is redirected to the login page.

## Depends on
- **Step 1 — Database setup**: the `users` table (`id`, `name`, `email UNIQUE`, `password_hash`, `created_at`), `get_db()` with `PRAGMA foreign_keys = ON`, and `init_db()` must exist and run at startup.

## Routes
- `GET /register` — renders the registration form (already implemented; no change to behaviour) — public
- `POST /register` — validates the submitted form, creates the user, redirects to `/login` on success or re-renders the form with an error on failure — public

## Database changes
No database changes. The existing `users` table already has every column needed (`name`, `email`, `password_hash`). Verified against `database/db.py`: `init_db()` creates `users` with `email TEXT NOT NULL UNIQUE`, so duplicate emails are rejected by the database as well as by the application check.

New helper functions to add to `database/db.py` (no SQL in routes):
- `get_user_by_email(email)` — returns the matching row or `None`. Uses `?` placeholders.
- `create_user(name, email, password_hash)` — inserts a user and returns the new `id`. Uses `?` placeholders.

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html`
    - Change the form `action="/register"` to `action="{{ url_for('register') }}"` (CLAUDE.md forbids hardcoded URLs).
    - Re-populate the `name` and `email` inputs with the submitted values on error (`value="{{ name or '' }}"`, `value="{{ email or '' }}"`). Never re-populate the password.
    - Keep the existing `{% if error %}` block; it already displays `error`.

## Files to change
- `app.py` — add `POST` handling to the `/register` route (keep `GET` rendering the form); import `request`, `redirect`, and `url_for` from Flask, and `generate_password_hash` from werkzeug, as needed.
- `database/db.py` — add `get_user_by_email()` and `create_user()`.
- `templates/register.html` — action URL and sticky field values as described above.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug` (already pinned in `requirements.txt`) provides `generate_password_hash`.

## Rules for implementation
- No SQLAlchemy or ORMs. Use `sqlite3` via `get_db()` only.
- Parameterised queries only: every SQL statement uses `?` placeholders; never f-strings or string concatenation in SQL.
- Passwords hashed with werkzeug: `generate_password_hash(password)`. Never store or log the plain password.
- Use CSS variables — never hardcode hex values. No new CSS is expected; reuse the existing `.auth-*`, `.form-*`, and `.btn-submit` classes. If a new style is needed, put it in a page-specific stylesheet, not inline.
- All templates extend `base.html`.
- Route functions do one thing: read the form, call validation, call DB helpers, and return a redirect or a rendered template. DB logic lives in `database/db.py`.
- Validation (in the route, before hashing):
  - `name`, `email`, and `password` are required; strip whitespace from `name` and `email`.
  - `email` is lowercased before lookup and insert.
  - `password` must be at least 8 characters (matches the placeholder "Min. 8 characters").
  - If `get_user_by_email()` returns a row, show an error ("An account with that email already exists.") — do not insert.
  - On any validation error, re-render `register.html` with `error` set and status code 400. Do not return raw strings.
- Use `abort()` for HTTP-level errors (for example a missing form method), not bare `return "error string"`.
- Use `url_for()` for every internal link and redirect target (`redirect(url_for('login'))`).
- Do not add sessions, login-after-register, or a flash system in this step.
- Do not implement any stub route (`/logout`, `/profile`, `/expenses/*`) in this step.
- Keep the app on port 5001.

## Definition of done
- [ ] `python app.py` starts without errors on http://127.0.0.1:5001.
- [ ] `GET /register` returns 200 and shows the form with the action pointing to `/register` (inspect the HTML: the form action is not a hardcoded string in the template).
- [ ] Submitting the form with a valid name, a new email, and an 8+ character password redirects (302) to `/login`.
- [ ] After that submission, the `users` table in `spendly.db` contains a row with the lowercased email and a `password_hash` that starts with `scrypt:` or `pbkdf2:` (werkzeug format) — the plain password does not appear anywhere in the table.
- [ ] Submitting the form with an email that already exists shows the "already exists" error on the page, returns HTTP 400, and does not create a new row.
- [ ] Submitting with a password shorter than 8 characters shows a validation error, returns HTTP 400, and does not create a row.
- [ ] Submitting with a blank name or email (whitespace only) shows a validation error and does not create a row.
- [ ] After a validation error, the name and email fields still contain the previously entered values; the password field is empty.
- [ ] Registering with `Test@Example.com` and then `test@example.com` is rejected as a duplicate.
- [ ] `GET /login` still renders the login page, and the stub routes `/logout`, `/profile`, `/expenses/add` still return their placeholder text (no regression).
- [ ] No SQL string in `app.py` (all DB access goes through `database/db.py`).
