"""Tests for Step 7: Add Expense (GET/POST /expenses/add)."""
import os
import re
import tempfile
from datetime import date, timedelta

import pytest
from werkzeug.security import generate_password_hash

import database.db as db_module

# Point the DB at a throwaway file BEFORE importing app (which runs init/seed at import).
_IMPORT_DB_DIR = tempfile.mkdtemp(prefix="spendly-import-")
db_module.DB_PATH = os.path.join(_IMPORT_DB_DIR, "import.db")

from app import app as flask_app  # noqa: E402
from database.db import CATEGORIES, create_user, get_db, init_db, seed_db  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADD_URL = "/expenses/add"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "test.db"))
    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test-secret"})
    init_db()
    seed_db()
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Tester"


@pytest.fixture
def user_id(app):
    return create_user("Fresh User", "fresh@example.com", generate_password_hash("pw12345"))


@pytest.fixture
def other_user_id(app):
    return create_user("Other User", "other@example.com", generate_password_hash("pw12345"))


@pytest.fixture
def auth_client(client, user_id):
    _login(client, user_id)
    return client


def _count_expenses(user_id=None):
    conn = get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _rows_for(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
    finally:
        conn.close()


def _form(**overrides):
    data = {
        "amount": "42.50",
        "category": "Food",
        "date": date.today().isoformat(),
        "description": "Test lunch",
    }
    data.update(overrides)
    return data


class TestAuthGuard:
    def test_get_logged_out_redirects_to_login(self, client):
        r = client.get(ADD_URL)
        assert r.status_code == 302, "Expected redirect when logged out"
        assert "/login" in r.headers["Location"]

    def test_post_logged_out_redirects_and_inserts_nothing(self, client):
        before = _count_expenses()
        r = client.post(ADD_URL, data=_form())
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]
        assert _count_expenses() == before, "No row may be inserted when logged out"


class TestFormRendering:
    def test_get_logged_in_renders_form_fields(self, auth_client):
        r = auth_client.get(ADD_URL)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in html, f"Missing field {field}"
        assert 'method="POST"' in html or 'method="post"' in html.lower()

    def test_get_extends_base_layout_with_nav_and_footer(self, auth_client):
        html = auth_client.get(ADD_URL).get_data(as_text=True).lower()
        assert "<nav" in html, "Expected nav from base layout"
        assert "<footer" in html, "Expected footer from base layout"

    def test_get_category_dropdown_lists_exactly_seven_categories(self, auth_client):
        html = auth_client.get(ADD_URL).get_data(as_text=True)
        assert len(CATEGORIES) == 7
        select = re.search(r"<select[^>]*>(.*?)</select>", html, re.S)
        assert select, "Expected a <select> element"
        options = re.findall(r"<option[^>]*>(.*?)</option>", select.group(1), re.S)
        names = [o.strip() for o in options if o.strip()]
        for cat in CATEGORIES:
            assert cat in names, f"Category {cat} missing from dropdown"
        assert len([n for n in names if n in CATEGORIES]) == 7

    def test_get_has_cancel_link_to_profile(self, auth_client):
        html = auth_client.get(ADD_URL).get_data(as_text=True)
        assert "Cancel" in html
        assert "/profile" in html


class TestSuccessfulSubmission:
    def test_valid_post_redirects_to_profile(self, auth_client):
        r = auth_client.post(ADD_URL, data=_form())
        assert r.status_code == 302
        assert r.headers["Location"].endswith("/profile")

    def test_valid_post_stores_row_for_logged_in_user(self, auth_client, user_id, other_user_id):
        other_before = _count_expenses(other_user_id)
        auth_client.post(ADD_URL, data=_form())
        rows = _rows_for(user_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == pytest.approx(42.50)
        assert row["category"] == "Food"
        assert row["date"] == date.today().isoformat()
        assert row["description"] == "Test lunch"
        assert _count_expenses(other_user_id) == other_before, "Must not affect other users"

    def test_expense_stored_against_session_user_not_another(self, client, other_user_id, user_id):
        _login(client, other_user_id)
        client.post(ADD_URL, data=_form(description="mine"))
        assert _count_expenses(other_user_id) == 1
        assert _count_expenses(user_id) == 0

    def test_new_expense_appears_on_profile(self, auth_client):
        auth_client.post(ADD_URL, data=_form(description="UniqueDescXyz", amount="77.77", category="Other"))
        r = auth_client.get("/profile")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert "UniqueDescXyz" in html, "New expense should be in transaction list"

    def test_category_breakdown_reflects_new_expense(self, auth_client):
        # Fresh user has no expenses, so the amount appears in list and breakdown/total.
        before = auth_client.get("/profile").get_data(as_text=True)
        assert "77.77" not in before
        auth_client.post(ADD_URL, data=_form(amount="77.77", category="Other", description="bk"))
        after = auth_client.get("/profile").get_data(as_text=True)
        assert after.count("77.77") >= 2, "Amount should show in list and category breakdown"

    def test_follow_redirect_lands_on_profile(self, auth_client):
        r = auth_client.post(ADD_URL, data=_form(), follow_redirects=True)
        assert r.status_code == 200

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_valid_category_accepted(self, auth_client, user_id, category):
        r = auth_client.post(ADD_URL, data=_form(category=category))
        assert r.status_code == 302
        assert _rows_for(user_id)[0]["category"] == category

    @pytest.mark.parametrize("amount", ["5", "0.01", "10.5", "10.50", "1000000"])
    def test_valid_amount_formats_accepted(self, auth_client, user_id, amount):
        r = auth_client.post(ADD_URL, data=_form(amount=amount))
        assert r.status_code == 302, f"Amount {amount} should be accepted"
        assert _rows_for(user_id)[0]["amount"] == pytest.approx(float(amount))

    def test_yesterday_date_accepted(self, auth_client, user_id):
        y = (date.today() - timedelta(days=1)).isoformat()
        r = auth_client.post(ADD_URL, data=_form(date=y))
        assert r.status_code == 302
        assert _rows_for(user_id)[0]["date"] == y

    def test_empty_description_accepted_and_stored_consistently(self, auth_client, user_id):
        r = auth_client.post(ADD_URL, data=_form(description=""))
        assert r.status_code == 302
        rows = _rows_for(user_id)
        assert len(rows) == 1
        assert rows[0]["description"] in (None, "")

    def test_missing_description_field_accepted(self, auth_client, user_id):
        data = _form()
        del data["description"]
        r = auth_client.post(ADD_URL, data=data)
        assert r.status_code == 302
        assert _count_expenses(user_id) == 1

    def test_description_is_trimmed(self, auth_client, user_id):
        auth_client.post(ADD_URL, data=_form(description="   padded   "))
        assert _rows_for(user_id)[0]["description"] == "padded"

    def test_description_exactly_200_chars_accepted(self, auth_client, user_id):
        r = auth_client.post(ADD_URL, data=_form(description="a" * 200))
        assert r.status_code == 302
        assert len(_rows_for(user_id)[0]["description"]) == 200

    def test_sql_injection_in_description_stored_literally(self, auth_client, user_id):
        payload = "x'); DROP TABLE expenses; --"
        r = auth_client.post(ADD_URL, data=_form(description=payload))
        assert r.status_code == 302
        assert _rows_for(user_id)[0]["description"] == payload
        assert _count_expenses() >= 1, "expenses table must still exist"


class TestValidationErrors:
    @pytest.mark.parametrize(
        "amount",
        ["0", "0.00", "-5", "-0.01", "abc", "", "   ", "10.123", "1.999", "1e2x"],
    )
    def test_invalid_amount_returns_400_and_no_insert(self, auth_client, user_id, amount):
        r = auth_client.post(ADD_URL, data=_form(amount=amount))
        assert r.status_code == 400, f"Amount {amount!r} should be rejected"
        assert _count_expenses(user_id) == 0

    def test_missing_amount_field_returns_400(self, auth_client, user_id):
        data = _form()
        del data["amount"]
        r = auth_client.post(ADD_URL, data=data)
        assert r.status_code == 400
        assert _count_expenses(user_id) == 0

    @pytest.mark.parametrize("category", ["Gambling", "", "food", "FOOD", "Food; DROP"])
    def test_invalid_category_returns_400_and_no_insert(self, auth_client, user_id, category):
        r = auth_client.post(ADD_URL, data=_form(category=category))
        assert r.status_code == 400, f"Category {category!r} should be rejected"
        assert _count_expenses(user_id) == 0

    def test_missing_category_field_returns_400(self, auth_client, user_id):
        data = _form()
        del data["category"]
        r = auth_client.post(ADD_URL, data=data)
        assert r.status_code == 400
        assert _count_expenses(user_id) == 0

    @pytest.mark.parametrize(
        "bad_date",
        ["2026-13-01", "2026-02-30", "not-a-date", "01/02/2026", "2026/01/02", "", "  "],
    )
    def test_malformed_or_empty_date_returns_400(self, auth_client, user_id, bad_date):
        r = auth_client.post(ADD_URL, data=_form(date=bad_date))
        assert r.status_code == 400, f"Date {bad_date!r} should be rejected"
        assert _count_expenses(user_id) == 0

    def test_missing_date_field_returns_400(self, auth_client, user_id):
        data = _form()
        del data["date"]
        r = auth_client.post(ADD_URL, data=data)
        assert r.status_code == 400
        assert _count_expenses(user_id) == 0

    def test_future_date_returns_400_and_no_insert(self, auth_client, user_id):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = auth_client.post(ADD_URL, data=_form(date=tomorrow))
        assert r.status_code == 400
        assert _count_expenses(user_id) == 0

    def test_description_over_200_chars_returns_400_and_no_insert(self, auth_client, user_id):
        r = auth_client.post(ADD_URL, data=_form(description="a" * 201))
        assert r.status_code == 400
        assert _count_expenses(user_id) == 0

    def test_error_response_shows_error_message_and_form(self, auth_client):
        r = auth_client.post(ADD_URL, data=_form(amount="0"))
        assert r.status_code == 400
        html = r.get_data(as_text=True)
        assert 'name="amount"' in html, "Form should be re-rendered"
        assert "error" in html.lower(), "An error message should be displayed"

    def test_submitted_values_preserved_on_error(self, auth_client):
        d = (date.today() - timedelta(days=3)).isoformat()
        r = auth_client.post(
            ADD_URL,
            data=_form(amount="10.123", date=d, description="keepMeDesc", category="Health"),
        )
        assert r.status_code == 400
        html = r.get_data(as_text=True)
        assert "10.123" in html, "Amount should be preserved"
        assert d in html, "Date should be preserved"
        assert "keepMeDesc" in html, "Description should be preserved"

    def test_submitted_category_preserved_on_error(self, auth_client):
        r = auth_client.post(ADD_URL, data=_form(amount="-1", category="Health"))
        assert r.status_code == 400
        html = r.get_data(as_text=True)
        m = re.search(r"<option[^>]*selected[^>]*>\s*Health", html) or re.search(
            r"<option[^>]*value=\"Health\"[^>]*selected", html
        )
        assert m, "Health should remain selected after error"


class TestPlaceholdersAndAssets:
    def test_edit_placeholder_unchanged(self, client):
        r = client.get("/expenses/1/edit")
        assert r.status_code == 200
        assert b"coming in Step 8" in r.data

    def test_delete_placeholder_unchanged(self, client):
        r = client.get("/expenses/1/delete")
        assert r.status_code == 200
        assert b"coming in Step 9" in r.data

    def test_add_expense_css_has_no_hardcoded_hex_colours(self):
        path = os.path.join(ROOT, "static", "css", "add-expense.css")
        assert os.path.exists(path), "static/css/add-expense.css must exist"
        with open(path, encoding="utf-8") as f:
            css = f.read()
        hexes = re.findall(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b", css)
        assert not hexes, f"Hardcoded hex colours found: {hexes}"

    def test_add_expense_template_has_no_inline_style_tag(self):
        path = os.path.join(ROOT, "templates", "add_expense.html")
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            assert "<style" not in f.read(), "No inline <style> tags allowed"
