"""Tests for Step 6: date filter on GET /profile (query params start / end)."""
import sqlite3

import pytest

import database.db as db_module
from app import app as flask_app
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

# user A expenses: (amount, category, date, description)
USER_A_EXPENSES = [
    (10.00, "Food", "2026-03-01", "desc-alpha"),
    (20.00, "Bills", "2026-03-05", "desc-bravo"),
    (30.00, "Food", "2026-03-10", "desc-charlie"),
    (40.00, "Bills", "2026-03-20", "desc-delta"),
]
USER_B_EXPENSE = (999.00, "Shopping", "2026-03-05", "desc-other-user")


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_spendly.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test-secret"})
    db_module.init_db()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            (1, "User A", "a@example.com", "x"),
        )
        conn.execute(
            "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
            (2, "User B", "b@example.com", "x"),
        )
        for amount, cat, d, desc in USER_A_EXPENSES:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (1, amount, cat, d, desc),
            )
        amount, cat, d, desc = USER_B_EXPENSE
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (2, amount, cat, d, desc),
        )
        conn.commit()
    finally:
        conn.close()
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["user_name"] = "User A"
    return client


def get_profile(client, **params):
    return client.get("/profile", query_string=params)


class TestAuthGuard:
    def test_unauthenticated_with_filter_redirects_to_login(self, client):
        resp = get_profile(client, start="2026-03-01", end="2026-03-10")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_with_invalid_filter_redirects_to_login(self, client):
        resp = get_profile(client, start="abc")
        assert resp.status_code == 302, "Auth guard should come before validation"
        assert "/login" in resp.headers["Location"]


class TestUnfiltered:
    def test_no_params_shows_all_user_expenses(self, auth_client):
        resp = get_profile(auth_client)
        assert resp.status_code == 200
        for _, _, _, desc in USER_A_EXPENSES:
            assert desc.encode() in resp.data, f"{desc} missing"
        assert "₹100.00".encode() in resp.data

    def test_no_params_excludes_other_users(self, auth_client):
        resp = get_profile(auth_client)
        assert b"desc-other-user" not in resp.data

    def test_empty_string_params_treated_as_not_supplied(self, auth_client):
        resp = get_profile(auth_client, start="", end="")
        assert resp.status_code == 200
        for _, _, _, desc in USER_A_EXPENSES:
            assert desc.encode() in resp.data

    def test_form_has_date_inputs_and_apply(self, auth_client):
        resp = get_profile(auth_client)
        assert b'type="date"' in resp.data
        assert b'name="start"' in resp.data
        assert b'name="end"' in resp.data
        assert b"Apply" in resp.data


class TestFilteredRange:
    def test_start_and_end_limits_transactions(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert resp.status_code == 200
        assert b"desc-alpha" in resp.data
        assert b"desc-bravo" in resp.data
        assert b"desc-charlie" in resp.data
        assert b"desc-delta" not in resp.data

    def test_range_stats_total(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert "₹60.00".encode() in resp.data
        assert "₹100.00".encode() not in resp.data

    def test_bounds_are_inclusive(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-05", end="2026-03-10")
        assert b"desc-bravo" in resp.data
        assert b"desc-charlie" in resp.data
        assert b"desc-alpha" not in resp.data
        assert b"desc-delta" not in resp.data

    def test_single_day_range(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-05", end="2026-03-05")
        assert b"desc-bravo" in resp.data
        assert b"desc-alpha" not in resp.data
        assert b"desc-charlie" not in resp.data

    def test_only_start_is_open_ended(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-10")
        assert b"desc-charlie" in resp.data
        assert b"desc-delta" in resp.data
        assert b"desc-alpha" not in resp.data
        assert b"desc-bravo" not in resp.data

    def test_only_end_is_open_ended(self, auth_client):
        resp = get_profile(auth_client, end="2026-03-05")
        assert b"desc-alpha" in resp.data
        assert b"desc-bravo" in resp.data
        assert b"desc-charlie" not in resp.data
        assert b"desc-delta" not in resp.data

    def test_filter_does_not_leak_other_users(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-05", end="2026-03-05")
        assert b"desc-other-user" not in resp.data

    def test_category_breakdown_reflects_range(self, auth_client):
        # Range contains only the Food (10 + 30) and Bills (20) rows.
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert b"Food" in resp.data
        assert b"Bills" in resp.data
        assert b"Shopping" not in resp.data

    def test_amounts_use_rupee_symbol(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert "₹".encode() in resp.data

    def test_inputs_prefilled_with_applied_values(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert b"2026-03-01" in resp.data
        assert b"2026-03-10" in resp.data
        assert b'value="2026-03-01"' in resp.data
        assert b'value="2026-03-10"' in resp.data

    def test_caption_shown_when_filter_active(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert b"Showing" in resp.data
        assert b"01 Mar 2026" in resp.data
        assert b"10 Mar 2026" in resp.data

    def test_caption_absent_when_no_filter(self, auth_client):
        resp = get_profile(auth_client)
        assert b"Showing 0" not in resp.data
        assert b"Showing 1" not in resp.data

    def test_clear_link_points_to_unfiltered_profile(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-01", end="2026-03-10")
        assert b"Clear" in resp.data
        assert b'href="/profile"' in resp.data


class TestEmptyRange:
    def test_no_matching_expenses_renders_without_error(self, auth_client):
        resp = get_profile(auth_client, start="2027-01-01", end="2027-01-31")
        assert resp.status_code == 200
        assert "₹0.00".encode() in resp.data
        for _, _, _, desc in USER_A_EXPENSES:
            assert desc.encode() not in resp.data

    def test_empty_range_shows_dash_top_category(self, auth_client):
        resp = get_profile(auth_client, start="2027-01-01", end="2027-01-31")
        assert "—".encode() in resp.data

    def test_empty_range_shows_empty_state_message(self, auth_client):
        resp = get_profile(auth_client, start="2027-01-01", end="2027-01-31")
        assert b"No transactions in this date range." in resp.data


class TestValidation:
    @pytest.mark.parametrize(
        "params",
        [
            {"start": "abc"},
            {"end": "abc"},
            {"start": "2026-13-40"},
            {"end": "2026-02-30"},
            {"start": "2026/03/01"},
            {"start": "01-03-2026"},
            {"start": "2026-03-01", "end": "not-a-date"},
            {"start": "2026-3-1x"},
            {"start": "2026-3-1"},
            {"end": "2026-03-1"},
            {"start": "2026-3-01"},
            {"start": "' OR 1=1 --"},
        ],
    )
    def test_malformed_date_returns_400(self, auth_client, params):
        resp = get_profile(auth_client, **params)
        assert resp.status_code == 400, f"Expected 400 for {params}"

    def test_start_after_end_returns_400(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-10", end="2026-03-01")
        assert resp.status_code == 400

    def test_start_equal_end_is_valid(self, auth_client):
        resp = get_profile(auth_client, start="2026-03-10", end="2026-03-10")
        assert resp.status_code == 200

    def test_malformed_start_with_empty_end_returns_400(self, auth_client):
        resp = get_profile(auth_client, start="abc", end="")
        assert resp.status_code == 400

    def test_sql_injection_attempt_does_not_alter_data(self, auth_client):
        get_profile(auth_client, start="2026-03-01'; DROP TABLE expenses; --")
        resp = get_profile(auth_client)
        assert resp.status_code == 200
        assert b"desc-alpha" in resp.data


class TestQueryHelpers:
    def test_summary_stats_unfiltered_still_works(self, app):
        stats = get_summary_stats(1)
        assert stats is not None

    def test_summary_stats_filtered_matches_empty_range(self, app):
        stats = get_summary_stats(1, start="2027-01-01", end="2027-01-31")
        assert stats is not None

    def test_recent_transactions_filtered_by_range(self, app):
        rows = get_recent_transactions(1, start="2026-03-01", end="2026-03-10")
        assert len(rows) == 3
        rows = get_recent_transactions(1, start="2026-03-10")
        assert len(rows) == 2
        rows = get_recent_transactions(1, end="2026-03-01")
        assert len(rows) == 1

    def test_recent_transactions_empty_range_returns_empty(self, app):
        rows = get_recent_transactions(1, start="2027-01-01", end="2027-01-31")
        assert len(rows) == 0

    def test_category_breakdown_empty_range_returns_empty(self, app):
        assert len(get_category_breakdown(1, start="2027-01-01", end="2027-01-31")) == 0

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"start": "2026-03-01", "end": "2026-03-10"},
            {"start": "2026-03-05"},
            {"end": "2026-03-10"},
        ],
    )
    def test_category_breakdown_percent_sums_to_100(self, app, kwargs):
        cats = get_category_breakdown(1, **kwargs)
        assert len(cats) > 0
        total = sum(c["percent"] for c in cats)
        assert total == 100, f"Percentages sum to {total} for {kwargs}"
