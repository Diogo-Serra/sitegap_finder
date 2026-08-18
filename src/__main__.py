"""SiteGap command-line interface."""

import argparse
import os
import sys
import time
from pathlib import Path

from src.config import DEFAULT_QUERIES, load_dotenv
from src.email_search import find_public_email
from src.places import Lead, PlacesError, search_without_website
from src.report import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sitegap",
        description="Find Google Places businesses with no website listed.",
    )
    parser.add_argument("location", help='Area to search, for example "Lisbon, Portugal"')
    parser.add_argument(
        "queries",
        nargs="*",
        help="Business categories; defaults to common local services",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum leads per category")
    parser.add_argument("--output", type=Path, default=Path("leads.txt"))
    parser.add_argument("--no-email-search", action="store_true")
    return parser.parse_args()


def collect_leads(api_key: str, location: str, queries: list[str], limit: int) -> list[Lead]:
    """Search each category and remove duplicate businesses."""
    unique_leads: dict[str, Lead] = {}
    for query in queries:
        print(f"Searching for {query} in {location}...", file=sys.stderr)
        for lead in search_without_website(api_key, query, location, limit):
            identity = lead["place_id"] or f'{lead["name"]}|{lead["address"]}'
            unique_leads.setdefault(identity, lead)
    return list(unique_leads.values())


def add_public_emails(leads: list[Lead]) -> None:
    """Enrich leads with public emails when a reliable match is found."""
    for index, lead in enumerate(leads, start=1):
        print(f"Checking email {index}/{len(leads)}: {lead['name']}...", file=sys.stderr)
        lead["email"] = find_public_email(lead["name"], lead["address"])
        time.sleep(0.5)


def main() -> int:
    args = parse_args()
    load_dotenv()
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("Error: add GOOGLE_PLACES_API_KEY to .env", file=sys.stderr)
        return 2
    if args.limit < 1:
        print("Error: --limit must be at least 1", file=sys.stderr)
        return 2

    try:
        leads = collect_leads(
            api_key,
            args.location,
            args.queries or list(DEFAULT_QUERIES),
            args.limit,
        )
    except PlacesError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if args.no_email_search:
        for lead in leads:
            lead["email"] = ""
    else:
        add_public_emails(leads)

    write_report(args.output, leads)
    print(f"Saved {len(leads)} leads to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
