"""Read-only query helpers for the profile page (Step 5).

No Flask imports here. Every helper calls get_db() and closes its connection
before returning. All SQL uses ? placeholders.
"""

import math
from datetime import datetime

from database.db import get_db


def _date_range_clause(start, end):
    """Build an optional date-range WHERE fragment.

    Only fixed SQL literals are concatenated; the bounds are returned as
    params for `?` placeholders.
    """
    clause, params = "", []
    if start:
        clause += " AND date >= ?"
        params.append(start)
    if end:
        clause += " AND date <= ?"
        params.append(end)
    return clause, params


# --- SECTION: user ----------------------------------------------------------

def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None

        name = row["name"]
        member_since = datetime.strptime(
            row["created_at"][:19], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
        initials = "".join(part[0] for part in name.split()[:2]).upper()

        return {
            "name": name,
            "email": row["email"],
            "member_since": member_since,
            "initials": initials,
        }
    finally:
        conn.close()


# --- SECTION: summary stats -------------------------------------------------

def get_summary_stats(user_id, start=None, end=None):
    range_sql, range_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?" + range_sql,
            (user_id, *range_params),
        ).fetchone()

        if totals["cnt"] == 0:
            return {
                "total_spent": 0.0,
                "transaction_count": 0,
                "top_category": "—",
            }

        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?" + range_sql + " "
            "GROUP BY category "
            "ORDER BY SUM(amount) DESC, category ASC "
            "LIMIT 1",
            (user_id, *range_params),
        ).fetchone()

        return {
            "total_spent": round(float(totals["total"]), 2),
            "transaction_count": int(totals["cnt"]),
            "top_category": top["category"],
        }
    finally:
        conn.close()


# --- SECTION: transactions --------------------------------------------------

def get_recent_transactions(user_id, limit=10, start=None, end=None):
    range_sql, range_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
            """ + range_sql + """
            ORDER BY date DESC, id DESC
            LIMIT ?
            """,
            (user_id, *range_params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %-d, %Y"),
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]


# --- SECTION: category breakdown --------------------------------------------

def get_category_breakdown(user_id, start=None, end=None):
    range_sql, range_params = _date_range_clause(start, end)
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category AS name, SUM(amount) AS total
            FROM expenses
            WHERE user_id = ?
            """ + range_sql + """
            GROUP BY category
            ORDER BY total DESC, name ASC
            """,
            (user_id, *range_params),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["total"] for row in rows)
    if grand_total == 0:
        return []

    breakdown = []
    for row in rows:
        raw_share = row["total"] / grand_total * 100
        breakdown.append({
            "name": row["name"],
            "total": round(row["total"], 2),
            "percent": math.floor(raw_share + 0.5),
        })

    # Push any rounding drift onto the largest category (first in the list)
    diff = 100 - sum(item["percent"] for item in breakdown)
    breakdown[0]["percent"] += diff

    return breakdown
