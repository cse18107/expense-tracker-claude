import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

with app.app_context():
    init_db()
    seed_db()


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


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Step 4: hardcoded placeholder data. Step 5 replaces these with DB queries.
    user_name = session.get("user_name", "Demo User")
    user = {
        "name": user_name,
        "email": "demo@spendly.com",
        "member_since": "January 2026",
        "initials": "".join(part[0] for part in user_name.split()[:2]).upper(),
    }
    stats = {
        "total_spent": 345.50,
        "transaction_count": 8,
        "top_category": "Bills",
    }
    transactions = [
        {"date": "Nov 1, 2026", "description": "Electricity bill", "category": "Bills", "amount": 120.00},
        {"date": "Nov 2, 2026", "description": "Lunch at cafe", "category": "Food", "amount": 12.50},
        {"date": "Nov 4, 2026", "description": "Metro card top-up", "category": "Transport", "amount": 25.00},
        {"date": "Nov 9, 2026", "description": "Weekly groceries", "category": "Food", "amount": 38.00},
        {"date": "Nov 12, 2026", "description": "Pharmacy", "category": "Health", "amount": 45.00},
        {"date": "Nov 15, 2026", "description": "Movie night", "category": "Entertainment", "amount": 30.00},
        {"date": "Nov 18, 2026", "description": "New shoes", "category": "Shopping", "amount": 60.00},
        {"date": "Nov 21, 2026", "description": "Miscellaneous", "category": "Other", "amount": 15.00},
    ]
    categories = [
        {"name": "Bills", "total": 120.00, "percent": 35},
        {"name": "Shopping", "total": 60.00, "percent": 17},
        {"name": "Food", "total": 50.50, "percent": 15},
        {"name": "Health", "total": 45.00, "percent": 13},
        {"name": "Entertainment", "total": 30.00, "percent": 9},
        {"name": "Transport", "total": 25.00, "percent": 7},
        {"name": "Other", "total": 15.00, "percent": 4},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
