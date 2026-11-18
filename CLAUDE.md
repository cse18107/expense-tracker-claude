# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker build with Flask and SQLite.

---

## Architecture
```
spendly/
|-- app.py                  # All routes - single file, no blueprint
|-- database/      
|   |___ db.py              # SQLite helpers: get_db(), init_db(), seed_db()
|-- templates/
|   |-- base.html           # Shared layout - all templates must extend this
|   |__ *.html              # One template per page
|-- static/
|   |-- css/
|   |   |-- style.css       # Global styles
|   |   |__ landing.css.    # Landing_page_only styles
|   |__ js/
|      |__ main.js          # Vanilla JS only
|__ requirements.txt

```

**Where  things belong:**
- New routes -> `app.py` only, no blueprints
- DB logic -> `database/db.py` only, never inline in routes
- New pages -> `.html` file extending `base.html`
- Page-specific styles -> new `.css` file, not inline `<style>` tags

---

## Code Style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every initernal link - never hardcode URLs
- Route functions: one responsibility only - fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) - never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

--- 

## Tech constraints

- **Flask only** - no FastAPI, no Django, no onther web frameworks
- **SQLite only** - no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** - no Reactt, no jQuery, no npm packages
- **No new pip packages** - work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed - f-strings and `match` statements are fine

---

## Commands

Run from the `spendly/` directory (the git root).

- Activate the existing venv: `source venv/bin/activate` (Python 3.14; venv is gitignored)
- Install dependencies: `pip install -r requirements.txt` (Flask 3.1.3, Werkzeug 3.1.6, pytest, pytest-flask)
- Run the dev server: `python app.py` — runs with `debug=True` on http://127.0.0.1:5001 (port 5001, not Flask's default 5000)
- Tests: none yet. `pytest` is in requirements but there is no `tests/` directory or test config. Once tests exist, run a single one with `pytest path/to/test_file.py::test_name`.
- Lint/format: no tooling configured.


---

## Implemented vs Stub Routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET /register` | Implemented — renders `register.html` |
| `GET /login` | Implemented — renders `login.html` |
| `GET /logout` | Implemented — clears session, redirects to `/` |
| `GET /profile` | Implemented — static UI with hardcoded data, login-protected (Step 4; DB wiring in Step 5) |
| `GET /expenses/add` | Stub — Step 7 |
| `GET /expenses/<id>/edit` | Stub — Step 8 |
| `GET /expenses/<id>/delete` | Stub — Step 9 |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and Things to Avoid

- **Never use raw string returns for stub routes** — once a step is implemented, always render a template.
- **Never hardcode URLs** in templates — always use `url_for()`.
- **Never put DB logic in route functions** — it belongs in `database/db.py`.
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync.
- **Never use JS frameworks** — the frontend is intentionally vanilla.
- **`database/db.py` is currently empty** — do not assume helpers exist until the step that implements them.
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection.
- The app runs on **port 5001**, not the Flask default 5000 — don't change this.