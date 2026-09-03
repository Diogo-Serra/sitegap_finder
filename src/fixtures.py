"""Sample data for --dry-run: exercise the full pipeline with no network calls.

This lets a new user verify the whole flow (Places filtering, website-gap
classification, email confidence scoring, caching, and report generation)
without an API key and without spending a single request.
"""

from typing import Any

SAMPLE_PLACES: list[dict[str, Any]] = [
    {
        "id": "dryrun-1",
        "displayName": {"text": "Clinica Dentaria Sorriso"},
        "formattedAddress": "Rua das Flores 10, Porto, Portugal",
        "nationalPhoneNumber": "220 100 001",
        "googleMapsUri": "https://maps.google.com/?cid=dryrun-1",
        # No websiteUri at all -> "no_website" gap.
    },
    {
        "id": "dryrun-2",
        "displayName": {"text": "Oficina do Zé"},
        "formattedAddress": "Avenida Central 22, Porto, Portugal",
        "nationalPhoneNumber": "220 100 002",
        "googleMapsUri": "https://maps.google.com/?cid=dryrun-2",
        "websiteUri": "https://www.facebook.com/oficinadoze",
        # Facebook-only "website" -> "social_only" gap.
    },
    {
        "id": "dryrun-3",
        "displayName": {"text": "Cabeleireiro Beleza Pura"},
        "formattedAddress": "Rua Nova 5, Porto, Portugal",
        "nationalPhoneNumber": "220 100 003",
        "googleMapsUri": "https://maps.google.com/?cid=dryrun-3",
        # No websiteUri -> "no_website" gap, no public email available.
    },
    {
        "id": "dryrun-4",
        "displayName": {"text": "Padaria Central"},
        "formattedAddress": "Praca do Comercio 1, Porto, Portugal",
        "nationalPhoneNumber": "220 100 004",
        "googleMapsUri": "https://maps.google.com/?cid=dryrun-4",
        "websiteUri": "https://padariacentral.pt",
        # Has a real website -> filtered out entirely, demonstrating the gap filter.
    },
]

# Keyed by business name; find_public_email() is only called for businesses
# that made it through the website-gap filter above.
SAMPLE_SEARCH_RESULTS: dict[str, str] = {
    "Clinica Dentaria Sorriso": (
        "<rss><channel><item>"
        "<title>Clinica Dentaria Sorriso - Porto</title>"
        "<description>Marcacoes: geral@clinicasorriso.pt</description>"
        "</item></channel></rss>"
    ),
    "Oficina do Zé": (
        "<rss><channel><item>"
        "<title>Oficina do Ze Porto</title>"
        "<description>Contacte-nos: oficinadoze@gmail.com</description>"
        "</item></channel></rss>"
    ),
}


def fetch_page(_api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fixture ``fetch_page`` returning the canned sample places once."""
    if payload.get("pageToken"):
        return {"places": []}
    return {"places": SAMPLE_PLACES}


def fetch_search(query: str) -> str:
    """Fixture ``fetch_search`` returning a canned result for known businesses."""
    for name, rss in SAMPLE_SEARCH_RESULTS.items():
        if name in query:
            return rss
    return ""
