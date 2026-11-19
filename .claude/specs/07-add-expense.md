# Spec: Add Expense

## Overview
Step 7 lets a logged-in user record a new expense through a form at
`/expenses/add`. The form collects amount, category, date, and an optional
description. On a valid submission the expense is inserted into the `expenses`
table for the current user and the user is redirected to the profile page, where
the new expense appears in the transaction history and category breakdown. This
is the first write path in Spendly: until now the app only reads expenses (seeded
data and the Step 6 date filter). Adding it completes the core loop of recording
and then reviewing spending, and it replaces the current placeholder string
returned by `GET /expenses/add`.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` constant in `database/db.py`)
- Step 2: Registration (users exist to own expenses)
- Step 3: Login / Logout (`session["user_id"]` identifies the user; protects the route)
- Step 5: Backend connection (`get_db()` helper and profile page that displays the result)

## Routes
- `GET /expenses/add` — renders the add-expense form — logged-in
- `POST /expenses/add` — validates the form, inserts the expense, redirects to `/profile` — logged-in

Behaviour:
- Unauthenticated `GET` or `POST` redirects to `url_for('login')`, matching `/profile`.
- On success, respond with `redirect(url_for('profile'))`.
- On validation failure, re-render `add_expense.html` with an `error` message and
  the submitted values preserved, with HTTP status 400 (same pattern as `/register`).
- Validation rules:
  - `amount` is required, must parse as a number, and must be greater than 0.
    Reject values with more than 2 decimal places.
  - `category` is required and must be one of `CATEGORIES` in `database/db.py`.
  - `date` is required, must be a real calendar date in `YYYY-MM-DD` format, and
    must not be in the future.
  - `description` is optional; trimmed; maximum 200 characters.
- Empty strings are treated as "not supplied".

## Database changes
No schema changes. The existing `expenses` table already has every required column
(`user_id`, `amount`, `category`, `date`, `description`).

Add one helper to `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts one row
  using `get_db()`, parameterised with `?` placeholders, commits, closes the
  connection, and returns `cursor.lastrowid`.

The route must call this helper; no SQL inside `app.py`.

## Templates
- **Create:** `templates/add_expense.html`
  - Extends `base.html`.
  - Form `method="POST"` with `action="{{ url_for('add_expense') }}"`.
  - Fields: `amount` (`type="number"`, `step="0.01"`, `min="0.01"`), `category`
    (`<select>` built from the `categories` list passed by the route), `date`
    (`type="date"`), `description` (`type="text"`, optional).
  - Shows `error` when present. Re-fills submitted values on error.
  - Submit button and a "Cancel" link to `url_for('profile')`.
  - Page-specific styles go in `static/css/add-expense.css`, linked from a
    `{% block head %}` block. No inline `<style>` tags.
- **Modify:** none

## Files to change
- `app.py` — replace the placeholder `add_expense` route with GET and POST handling.
  Import `create_expense` and `CATEGORIES` from `database/db.py`.
- `database/db.py` — add `create_expense()`.

## Files to create
- `templates/add_expense.html` — the form page.
- `static/css/add-expense.css` — styles specific to the form page.
- `.claude/specs/07-add-expense.md` — this spec (already saved).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs. Use `sqlite3` through `get_db()` only.
- Parameterised queries only: `?` placeholders, never f-strings or `.format()` in SQL.
- Passwords hashed with werkzeug. Not applicable to this feature; do not touch auth code.
- Use CSS variables from `static/css/style.css` (for example `var(--accent)`,
  `var(--border)`, `var(--danger)`, `var(--radius-md)`). Never hardcode hex values
  in `add-expense.css` or the template.
- All templates extend `base.html`.
- All internal links use `url_for()`. No hardcoded URLs.
- Route functions do one thing: validate input via a small helper, call
  `create_expense()` or render the template, then return. No DB logic in routes.
- Validation failures re-render the form with status 400 (as `/register` does).
  Use `abort()` only for unexpected HTTP errors. Do not return bare error strings.
- Use `CATEGORIES` from `database/db.py` as the single source of truth for valid
  categories. Do not duplicate the list in the route or template.
- Do not change the port (5001) or any other route.
- Do not implement Step 8 (`/expenses/<id>/edit`) or Step 9 (`/expenses/<id>/delete`).
  Leave their placeholder routes unchanged.

## Definition of done
- [ ] Logged out, `GET /expenses/add` redirects to `/login`.
- [ ] Logged out, `POST /expenses/add` redirects to `/login` and inserts nothing.
- [ ] Logged in, `GET /expenses/add` renders a form with amount, category, date, and
      description fields. The page extends the base layout (nav and footer visible).
- [ ] The category dropdown lists exactly the seven values in `CATEGORIES`.
- [ ] Submitting a valid expense (e.g. amount `42.50`, category `Food`, today's date,
      description `Test lunch`) redirects to `/profile`, and the new expense appears in
      the transaction list.
- [ ] The category breakdown on `/profile` increases for the chosen category after a
      successful submission.
- [ ] Submitting with amount `0`, a negative amount, or `abc` re-renders the form with
      HTTP 400 and an error message, and no row is inserted.
- [ ] Submitting with amount `10.123` (more than 2 decimals) re-renders with HTTP 400.
- [ ] Submitting with a category not in `CATEGORIES` (e.g. edited via DevTools to
      `Gambling`) re-renders with HTTP 400.
- [ ] Submitting with a missing or malformed date (e.g. `2026-13-01`) re-renders with
      HTTP 400.
- [ ] Submitting with a future date re-renders with HTTP 400.
- [ ] Submitting with a description longer than 200 characters re-renders with HTTP 400.
- [ ] An empty description is accepted and stored as NULL (or empty string, consistently).
- [ ] On validation error, the previously entered amount, date, and description are
      still in the form fields.
- [ ] `static/css/add-expense.css` contains no hardcoded hex colours; all colours come
      from CSS variables defined in `style.css`.
- [ ] The app starts with `python app.py` on http://127.0.0.1:5001 with no errors.
- [ ] `GET /expenses/<id>/edit` and `GET /expenses/<id>/delete` still return their
      placeholder strings (Steps 8 and 9 not implemented).
