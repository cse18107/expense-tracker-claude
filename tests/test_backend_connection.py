"""Tests for Step 5: profile page wired to the database.

Every test runs against a temporary SQLite file, never the real spendly.db.
Run from the repo root with: python -m pytest tests/test_backend_connection.py
"""

import sys

import pytest
from werkzeug.security import generate_password_hash

import database.db as db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a fresh temp database with the seed data loaded."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    return db.DB_PATH


@pytest.fixture
def client(temp_db, monkeypatch):
    """Flask test client. app is imported fresh so its startup uses temp_db."""
    monkeypatch.delitem(sys.modules, "app", raising=False)
    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _seed_user_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


def _new_user(name="Test Person", email="test@example.com"):
    return db.create_user(name, email, generate_password_hash("secret123"))


def _login(client, user_id, name):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = name


# ---------------------------------------------------------------- unit: user

def test_get_user_by_id_returns_user_fields(temp_db):
    user = get_user_by_id(_seed_user_id())
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["initials"] == "DU"
    assert user["member_since"] and len(user["member_since"].split()) == 2
    assert "password_hash" not in user


def test_get_user_by_id_missing_returns_none(temp_db):
    assert get_user_by_id(99999) is None


# -------------------------------------------------------------- unit: stats

def test_get_summary_stats_with_expenses(temp_db):
    stats = get_summary_stats(_seed_user_id())
    assert stats["total_spent"] == 345.50
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(temp_db):
    user_id = _new_user()
    assert get_summary_stats(user_id) == {
        "total_spent": 0.0,
        "transaction_count": 0,
        "top_category": "—",
    }


# ------------------------------------------------------ unit: transactions

def test_get_recent_transactions_newest_first(temp_db):
    rows = get_recent_transactions(_seed_user_id())
    assert len(rows) == 8
    assert {"date", "description", "category", "amount"} <= set(rows[0])
    # Seed dates are day 1..21 of the current month; newest first means day 21 first.
    assert rows[0]["description"] == "Miscellaneous"
    assert rows[-1]["description"] == "Electricity bill"


def test_get_recent_transactions_respects_limit(temp_db):
    assert len(get_recent_transactions(_seed_user_id(), limit=3)) == 3


def test_get_recent_transactions_no_expenses(temp_db):
    assert get_recent_transactions(_new_user()) == []


# ------------------------------------------------------- unit: categories

def test_get_category_breakdown_sums_to_100(temp_db):
    breakdown = get_category_breakdown(_seed_user_id())
    assert len(breakdown) == 7
    totals = [item["total"] for item in breakdown]
    assert totals == sorted(totals, reverse=True)
    assert all(isinstance(item["percent"], int) for item in breakdown)
    assert sum(item["percent"] for item in breakdown) == 100


def test_get_category_breakdown_no_expenses(temp_db):
    assert get_category_breakdown(_new_user()) == []


# ------------------------------------------------------------- route tests

def test_profile_logged_out_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_seed_user_shows_db_data(client):
    _login(client, _seed_user_id(), "Demo User")
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹345.50" in html
    assert "₹" in html
    assert "Bills" in html
    assert "Miscellaneous" in html  # newest seeded transaction shows up
    assert "346.24" not in html  # the old wrong total must not appear


def test_profile_new_user_shows_zero_state(client):
    user_id = _new_user(name="Fresh User", email="fresh@example.com")
    _login(client, user_id, "Fresh User")
    response = client.get("/profile")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Fresh User" in html
    assert "₹0.00" in html
    assert "No transactions yet" in html
    assert "No spending to break down yet" in html
    assert "<table" not in html
    assert "category-list" not in html


def test_profile_users_only_see_their_own_data(client):
    other_id = _new_user(name="Other Person", email="other@example.com")
    conn = db.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (other_id, 999.00, "Other", "2026-11-05", "Secret purchase"),
    )
    conn.commit()
    conn.close()

    _login(client, other_id, "Other Person")
    html = client.get("/profile").get_data(as_text=True)
    assert "Secret purchase" in html
    assert "Electricity bill" not in html
    assert "₹999.00" in html
    assert "₹345.50" not in html


def test_profile_deleted_user_clears_session(client):
    _login(client, 99999, "Ghost")
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
