import os
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_db,
    get_user_by_email,
    init_db,
    seed_db,
)
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

with app.app_context():
    init_db()
    seed_db()


def login_required(view):
    """Redirect to the login page when the session has no logged-in user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    error = None
    if not name or not email or not password or not confirm_password:
        error = "All fields are required."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm_password:
        error = "Passwords do not match."
    elif get_user_by_email(email) is not None:
        error = "An account with that email already exists."

    if error:
        return render_template(
            "register.html", error=error, name=name, email=email
        ), 400

    try:
        create_user(name, email, generate_password_hash(password))
    except sqlite3.IntegrityError:
        return render_template(
            "register.html",
            error="An account with that email already exists.",
            name=name,
            email=email,
        ), 400

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html", error="All fields are required.", email=email
        ), 400

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        ), 400

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


DATE_PARAM_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _parse_date_range():
    """Read optional `start`/`end` query params as dates.

    Returns (start_date, end_date), each None when not supplied. Aborts with
    400 when a value is not a zero-padded YYYY-MM-DD date, or when start is
    after end.
    """
    dates = []
    for name in ("start", "end"):
        raw = request.args.get(name, "").strip()
        if not raw:
            dates.append(None)
            continue
        if not DATE_PARAM_PATTERN.fullmatch(raw):
            abort(400)
        try:
            dates.append(datetime.strptime(raw, "%Y-%m-%d").date())
        except ValueError:
            abort(400)

    start_date, end_date = dates
    if start_date and end_date and start_date > end_date:
        abort(400)
    return start_date, end_date


@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    start_date, end_date = _parse_date_range()
    start = start_date.isoformat() if start_date else None
    end = end_date.isoformat() if end_date else None

    return render_template(
        "profile.html",
        user=user,
        stats=get_summary_stats(user_id, start=start, end=end),
        transactions=get_recent_transactions(user_id, start=start, end=end),
        categories=get_category_breakdown(user_id, start=start, end=end),
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


MAX_DESCRIPTION_LENGTH = 200
MAX_AMOUNT = Decimal("1000000000")


def _parse_amount(raw):
    """Return the amount as a Decimal, or raise ValueError with a user message."""
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise ValueError("Amount must be a number.") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    # Checked before quantize(): quantize raises on huge exponents such as 1e999999.
    if amount > MAX_AMOUNT:
        raise ValueError("Amount is too large.")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Amount can have at most 2 decimal places.")
    return amount


def _parse_date(raw):
    """Return the date, or raise ValueError with a user message."""
    try:
        # The regex rejects loose formats that strptime would accept.
        if not DATE_PARAM_PATTERN.fullmatch(raw):
            raise ValueError
        parsed = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Date must be a valid YYYY-MM-DD date.") from None
    if parsed > date.today():
        raise ValueError("Date cannot be in the future.")
    return parsed


def _validate_expense_form(form):
    """Validate add-expense form fields.

    Returns (clean_values, None) when valid, or (None, error_message) otherwise.
    Stored values are: amount (float), category, date (YYYY-MM-DD), description
    (None when empty).
    """
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    date_raw = form.get("date", "").strip()
    description = form.get("description", "").strip()

    if not amount_raw or not category or not date_raw:
        return None, "Amount, category and date are required."

    try:
        amount = _parse_amount(amount_raw)
        if category not in CATEGORIES:
            raise ValueError("Please choose a valid category.")
        expense_date = _parse_date(date_raw)
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
            )
    except ValueError as exc:
        return None, str(exc)

    # Money is validated as Decimal above, then stored as float because the
    # expenses.amount column is REAL.
    cleaned = {
        "amount": float(amount),
        "category": category,
        "expense_date": expense_date.isoformat(),
        "description": description or None,
    }
    return cleaned, None


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    today = date.today().isoformat()
    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            max_description_length=MAX_DESCRIPTION_LENGTH,
            form={},
        )

    expense, error = _validate_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            error=error,
            categories=CATEGORIES,
            today=today,
            max_description_length=MAX_DESCRIPTION_LENGTH,
            form=request.form,
        ), 400

    try:
        create_expense(session["user_id"], **expense)
    except sqlite3.IntegrityError:
        # The session points at a user who no longer exists (deleted or DB reset).
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
