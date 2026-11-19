# Spec: Date Filter for Profile Page

## Overview
Step 6 lets a logged-in user narrow the profile page to a date range. The page
gets a "from" and "to" date control; when set, the summary stats, transaction
history, and category breakdown all reflect only expenses whose `date` falls in
that range. With no filter, the page behaves exactly as it does after Step 5.
This matters at this stage of the roadmap because the profile now shows real
data, and users with months of expenses need a way to look at one period
without leaving the page.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column)
- Step 3: Login / Logout (`session["user_id"]` identifies the user)
- Step 4: Profile page static UI (filter controls are placed in the existing layout)
- Step 5: Backend connection (stats, transactions, and breakdown are DB-backed)

## Routes
No new routes. The existing `GET /profile` route is modified to read optional
query parameters `start` and `end` (ISO `YYYY-MM-DD`):

- `GET /profile?start=YYYY-MM-DD&end=YYYY-MM-DD` — shows the profile filtered to the range — logged-in
- `GET /profile` — unfiltered, identical to Step 5 — logged-in

Validation behaviour:
- Either parameter may be supplied alone (open-ended range).
- A malformed date (not `YYYY-MM-DD` or not a real calendar date) returns `abort(400)`.
- If `start` is later than `end`, return `abort(400)`.
- Empty-string parameters are treated as "not supplied".

## Database changes
No database changes. The `expenses.date` column is already stored as
`YYYY-MM-DD` TEXT, which compares correctly as a string for range filtering.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a GET form above the stats block with two `<input type="date">` fields
    (`name="start"`, `name="end"`), an Apply submit button, and a "Clear" link
    to `url_for('profile')`.
  - Pre-fill the inputs with the currently applied `start` / `end` values.
  - Show a short caption (e.g. "Showing 01 Nov 2026 – 19 Nov 2026") when a
    filter is active.
  - Empty-state messages should read correctly when a filter yields no rows
    (e.g. "No transactions in this date range.").
- **Modify:** `static/css/profile.css`
  - Styles for the filter form, using existing CSS variables only.

## Files to change
- `app.py` — `profile()` reads and validates `start` / `end`, passes them to
  the query helpers, and passes the applied values back to the template.
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown` each gain optional `start=None, end=None` keyword
  arguments. When supplied, add `AND date >= ?` and/or `AND date <= ?` to the
  WHERE clause.
- `templates/profile.html` — filter form, active-range caption, empty-state text.
- `static/css/profile.css` — filter form styles.

## Files to create
- `.claude/specs/06-date-filter-for-profile-page.md` — this spec (already created).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — date bounds are passed as `?` parameters, never
  f-stringed into the SQL
- Date validation belongs in the route (or a small helper in `app.py`), not in
  SQL. Use `datetime.strptime(value, "%Y-%m-%d")` and `abort(400)` on failure
- Route functions stay single-responsibility: parse params, call queries, render
- Query helpers must still call `get_db()` internally and close the connection
  before returning
- The filter must apply to all three sections (stats, transactions, breakdown)
  consistently — no section may ignore the range
- `percent` values in the category breakdown must still sum to 100 after filtering
- With no expenses in range, stats return zeros and lists return empty, without exceptions
- Use CSS variables — never hardcode hex values
- No inline styles
- All templates extend `base.html`
- All internal links and the form action use `url_for()`
- Currency must always display as ₹
- Do not implement any stub route (`/expenses/add`, edit, delete)

## Definition of done
- [ ] Logged-in user visiting `/profile` with no parameters sees the same numbers as before this step (seed user: ₹345.50, 8 transactions, top category "Bills")
- [ ] The filter form shows two date inputs and an Apply button above the stats
- [ ] Setting `start` and `end` to a window that covers only some seed expenses (e.g. the first day of the current month through the 10th, which includes the seed rows dated 1, 2, 4, and 9) limits stats, transactions, and breakdown to only those expenses (seed rows are dated in the current month, days 1–21)
- [ ] Setting only `start` returns expenses on or after that date; setting only `end` returns expenses on or before that date
- [ ] Setting a range with no matching expenses shows ₹0.00, 0 transactions, "—" top category, the empty-state messages, and no errors
- [ ] `start` later than `end` returns HTTP 400
- [ ] A malformed date such as `start=2026-13-40` or `start=abc` returns HTTP 400
- [ ] Inputs are pre-filled with the applied range after submitting the form
- [ ] "Clear" link returns to `/profile` with no filter applied
- [ ] Unauthenticated `GET /profile?start=...` still redirects to `/login` (302)
- [ ] Category breakdown percentages still sum to 100 for a filtered range
- [ ] All amounts still display with ₹
- [ ] App still runs on port 5001 with `python app.py`
