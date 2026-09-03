"""SQLite persistence for leads across runs.

Caching lets repeat runs skip email lookups for businesses that were
already checked recently, and builds a growing, de-duplicated database of
website gaps that can be exported at any time.
"""

import datetime
import sqlite3
from pathlib import Path
from typing import Any, cast


Lead = dict[str, str]

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    place_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,
    address TEXT,
    phone TEXT,
    google_maps_url TEXT,
    website_gap_reason TEXT,
    social_url TEXT,
    email TEXT,
    email_confidence TEXT,
    email_source TEXT,
    search_query TEXT,
    first_seen TEXT NOT NULL,
    last_checked TEXT
)
"""


def connect(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the lead cache database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def upsert_lead(conn: sqlite3.Connection, lead: Lead) -> None:
    """Insert a newly-found lead, or refresh its business details if known."""
    place_id = lead.get("place_id") or ""
    if not place_id:
        return
    existing = conn.execute(
        "SELECT place_id FROM leads WHERE place_id = ?", (place_id,)
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO leads (
                place_id, name, category, address, phone, google_maps_url,
                website_gap_reason, social_url, search_query, first_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                place_id,
                lead.get("name", ""),
                lead.get("category", ""),
                lead.get("address", ""),
                lead.get("phone", ""),
                lead.get("google_maps_url", ""),
                lead.get("website_gap_reason", ""),
                lead.get("social_url", ""),
                lead.get("search_query", ""),
                _now(),
            ),
        )
    else:
        conn.execute(
            """
            UPDATE leads SET name = ?, category = ?, address = ?, phone = ?,
                google_maps_url = ?, website_gap_reason = ?, social_url = ?
            WHERE place_id = ?
            """,
            (
                lead.get("name", ""),
                lead.get("category", ""),
                lead.get("address", ""),
                lead.get("phone", ""),
                lead.get("google_maps_url", ""),
                lead.get("website_gap_reason", ""),
                lead.get("social_url", ""),
                place_id,
            ),
        )
    conn.commit()


def get_email_check(conn: sqlite3.Connection, place_id: str) -> sqlite3.Row | None:
    """Return the cached email lookup result for a place, if any."""
    row = conn.execute(
        "SELECT email, email_confidence, email_source, last_checked "
        "FROM leads WHERE place_id = ?",
        (place_id,),
    ).fetchone()
    return cast("sqlite3.Row | None", row)


def is_email_check_fresh(row: sqlite3.Row | None, refresh_days: int) -> bool:
    """Return True when a cached email lookup is still within the freshness window."""
    if row is None or row["last_checked"] is None:
        return False
    checked_at = datetime.datetime.fromisoformat(row["last_checked"])
    age = datetime.datetime.now(datetime.timezone.utc) - checked_at
    return age <= datetime.timedelta(days=refresh_days)


def record_email_check(
    conn: sqlite3.Connection,
    place_id: str,
    email: str,
    confidence: str,
    source: str,
) -> None:
    """Persist the outcome of an email lookup, even when nothing was found."""
    conn.execute(
        """
        UPDATE leads
        SET email = ?, email_confidence = ?, email_source = ?, last_checked = ?
        WHERE place_id = ?
        """,
        (email, confidence, source, _now(), place_id),
    )
    conn.commit()


def export_all(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return every cached lead as a plain dict, most recently seen first."""
    rows = conn.execute("SELECT * FROM leads ORDER BY first_seen DESC").fetchall()
    return [dict(row) for row in rows]
