"""SiteGap command-line interface."""

import argparse
import csv
import logging
import os
import sqlite3
import sys
import time
from pathlib import Path

from src import cache, fixtures
from src.config import DEFAULT_CACHE_PATH, DEFAULT_QUERIES, DEFAULT_REFRESH_DAYS, load_dotenv
from src.email_search import FetchSearch, find_public_email, request_search
from src.places import FetchPage, Lead, PlacesError, request_page, search_without_website
from src.report import summarize, write_report

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sitegap",
        description="Find Google Places businesses with no website listed.",
    )
    parser.add_argument(
        "location", nargs="?", help='Area to search, for example "Lisbon, Portugal"'
    )
    parser.add_argument(
        "queries",
        nargs="*",
        help="Business categories; defaults to common local services",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum leads per category")
    parser.add_argument("--output", type=Path, default=Path("leads.txt"))
    parser.add_argument("--no-email-search", action="store_true")
    parser.add_argument(
        "--cache-db",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="SQLite file used to remember leads and emails across runs",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable the lead cache")
    parser.add_argument(
        "--refresh-emails",
        action="store_true",
        help="Re-run email lookups even if a cached result exists",
    )
    parser.add_argument(
        "--refresh-days",
        type=int,
        default=DEFAULT_REFRESH_DAYS,
        help="Reuse a cached email lookup younger than this many days (default: %(default)s)",
    )
    parser.add_argument(
        "--export-cache",
        type=Path,
        help="Write every cached lead to a CSV file and exit, without searching",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logging")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the full pipeline on built-in sample data; no API key or network needed",
    )
    return parser.parse_args()


def collect_leads(
    api_key: str,
    location: str,
    queries: list[str],
    limit: int,
    fetch_page: FetchPage | None = None,
) -> list[Lead]:
    """Search each category and remove duplicate businesses."""
    unique_leads: dict[str, Lead] = {}
    for query in queries:
        print(f"Searching for {query} in {location}...", file=sys.stderr)
        page_fetcher = fetch_page if fetch_page is not None else request_page
        for lead in search_without_website(api_key, query, location, limit, page_fetcher):
            identity = lead["place_id"] or f'{lead["name"]}|{lead["address"]}'
            unique_leads.setdefault(identity, lead)
    return list(unique_leads.values())


def add_public_emails(
    leads: list[Lead],
    conn: sqlite3.Connection | None,
    *,
    refresh_emails: bool,
    refresh_days: int,
    fetch_search: FetchSearch | None = None,
) -> None:
    """Enrich leads with public emails, reusing fresh cached results."""
    for index, lead in enumerate(leads, start=1):
        place_id = lead.get("place_id", "")
        cached = cache.get_email_check(conn, place_id) if conn is not None and place_id else None

        cached_is_fresh = cache.is_email_check_fresh(cached, refresh_days)
        if cached is not None and not refresh_emails and cached_is_fresh:
            lead["email"] = cached["email"] or ""
            lead["email_confidence"] = cached["email_confidence"] or ""
            lead["email_source"] = cached["email_source"] or ""
            print(f"Using cached email {index}/{len(leads)}: {lead['name']}...", file=sys.stderr)
            continue

        print(f"Checking email {index}/{len(leads)}: {lead['name']}...", file=sys.stderr)
        search_fetcher = fetch_search if fetch_search is not None else request_search
        match = find_public_email(lead["name"], lead["address"], search_fetcher)
        lead["email"] = match.email
        lead["email_confidence"] = match.confidence
        lead["email_source"] = match.source
        if conn is not None and place_id:
            cache.record_email_check(conn, place_id, match.email, match.confidence, match.source)
        if fetch_search is None:
            time.sleep(0.5)


def export_cache(db_path: Path, output: Path) -> int:
    """Dump every cached lead to a CSV file."""
    if not db_path.is_file():
        print(f"Error: cache database not found at {db_path}", file=sys.stderr)
        return 1
    conn = cache.connect(db_path)
    rows = cache.export_all(conn)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)
    print(f"Exported {len(rows)} cached leads to {output}")
    return 0


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    load_dotenv()

    if args.export_cache:
        return export_cache(args.cache_db, args.export_cache)

    if not args.location:
        print("Error: a location is required unless using --export-cache", file=sys.stderr)
        return 2
    if args.limit < 1:
        print("Error: --limit must be at least 1", file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            "Dry run: using built-in sample data, no API key or network needed.",
            file=sys.stderr,
        )
        api_key = "dry-run"
        page_fetcher: FetchPage | None = fixtures.fetch_page
        search_fetcher: FetchSearch | None = fixtures.fetch_search
        cache_db = (
            args.cache_db
            if args.cache_db != DEFAULT_CACHE_PATH
            else Path("sitegap_dry_run_cache.db")
        )
    else:
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
        if not api_key:
            print("Error: add GOOGLE_PLACES_API_KEY to .env", file=sys.stderr)
            return 2
        page_fetcher = None
        search_fetcher = None
        cache_db = args.cache_db

    try:
        leads = collect_leads(
            api_key,
            args.location,
            args.queries or list(DEFAULT_QUERIES),
            args.limit,
            page_fetcher,
        )
    except PlacesError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    conn = None if args.no_cache else cache.connect(cache_db)
    if conn is not None:
        for lead in leads:
            cache.upsert_lead(conn, lead)

    if args.no_email_search:
        for lead in leads:
            lead["email"] = ""
            lead["email_confidence"] = ""
            lead["email_source"] = ""
    else:
        add_public_emails(
            leads,
            conn,
            refresh_emails=args.refresh_emails,
            refresh_days=args.refresh_days,
            fetch_search=search_fetcher,
        )

    write_report(args.output, leads)
    print(f"Saved {len(leads)} leads to {args.output}")
    print(summarize(leads), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
