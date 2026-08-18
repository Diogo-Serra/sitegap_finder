"""Google Places search and filtering."""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable


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


class PlacesError(RuntimeError):
    """Raised when Google Places cannot complete a request."""


def request_page(api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELDS,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result: dict[str, Any] = json.load(response)
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
            if place.get("websiteUri"):
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
                }
            )
            if len(leads) >= limit:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)

    return leads
