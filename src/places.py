"""Google Places search and filtering."""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from src.http import fetch, random_user_agent

logger = logging.getLogger(__name__)

API_URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.internationalPhoneNumber",
        "places.nationalPhoneNumber",
        "places.googleMapsUri",
        "places.websiteUri",
        "places.primaryType",
        "nextPageToken",
    )
)
Lead = dict[str, str]
FetchPage = Callable[[str, dict[str, Any]], dict[str, Any]]

# Hosts that Google Places lists as a "website" but that are really just a
# social profile or a free auto-generated page, not a real business site.
# Businesses that only have one of these still count as a website gap.
PLACEHOLDER_WEBSITE_HOSTS = frozenset(
    {
        "facebook.com",
        "m.facebook.com",
        "business.facebook.com",
        "instagram.com",
        "linktr.ee",
        "wa.me",
        "api.whatsapp.com",
        "m.me",
        "bio.link",
        "beacons.ai",
    }
)
PLACEHOLDER_WEBSITE_SUFFIXES = (".business.site",)


class PlacesError(RuntimeError):
    """Raised when Google Places cannot complete a request."""


def classify_website(website_uri: str) -> tuple[bool, str]:
    """Classify a Places ``websiteUri`` as a website gap, or not.

    Returns ``(is_gap, reason)`` where ``reason`` is ``"no_website"``,
    ``"social_only"``, or ``""`` when a real website is present.
    """
    if not website_uri:
        return True, "no_website"

    host = urllib.parse.urlparse(website_uri).netloc.lower().removeprefix("www.")
    if host in PLACEHOLDER_WEBSITE_HOSTS or host.endswith(PLACEHOLDER_WEBSITE_SUFFIXES):
        return True, "social_only"

    return False, ""


def request_page(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")

    def build_request() -> urllib.request.Request:
        return urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": FIELDS,
                "User-Agent": random_user_agent(),
            },
            method="POST",
        )

    try:
        data = fetch(build_request, attempts=3, timeout=30)
        result: dict[str, Any] = json.loads(data)
        return result
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise PlacesError(
            f"Google Places returned HTTP {error.code}: {details}"
        ) from error
    except urllib.error.URLError as error:
        raise PlacesError(f"Could not contact Google Places: {error.reason}") from error


def search_without_website(
    api_key: str,
    query: str,
    location: str,
    limit: int,
    fetch_page: FetchPage = request_page,
) -> list[Lead]:
    """Return Places listings where Google provides no website."""
    leads: list[Lead] = []
    page_token: str | None = None

    while len(leads) < limit:
        payload: dict[str, Any] = {
            "textQuery": f"{query} in {location}",
            "pageSize": min(20, limit),
        }
        if page_token:
            payload["pageToken"] = page_token

        data = fetch_page(api_key, payload)
        for place in data.get("places", []):
            website_uri = place.get("websiteUri", "")
            is_gap, reason = classify_website(website_uri)
            if not is_gap:
                continue

            phone = place.get("internationalPhoneNumber") or place.get(
                "nationalPhoneNumber", ""
            )
            maps_url = place.get("googleMapsUri", "")
            if not phone and not maps_url:
                continue

            leads.append(
                {
                    "name": place.get("displayName", {}).get("text", ""),
                    "category": place.get("primaryType", ""),
                    "address": place.get("formattedAddress", ""),
                    "phone": phone,
                    "google_maps_url": maps_url,
                    "search_query": query,
                    "place_id": place.get("id", ""),
                    "website_gap_reason": reason,
                    "social_url": website_uri if reason == "social_only" else "",
                }
            )
            if len(leads) >= limit:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)

    return leads
