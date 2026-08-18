"""Public email discovery from indexed search results."""

import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable


SEARCH_URL = "https://www.bing.com/search"
EMAIL_PATTERN = re.compile(
    r"[A-Z0-9._%+-]+@(?:gmail\.com|hotmail\.(?:com|pt)|outlook\.(?:com|pt)|live\.com|sapo\.pt)",
    re.IGNORECASE,
)
FetchSearch = Callable[[str], str]


def request_search(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "format": "rss", "count": 10})
    request = urllib.request.Request(
        f"{SEARCH_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0 (compatible; SiteGapFinder/0.1)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result: str = response.read().decode("utf-8", errors="replace")
            return result
    except (urllib.error.HTTPError, urllib.error.URLError):
        return ""


def find_public_email(
    business_name: str,
    address: str,
    fetch_search: FetchSearch = request_search,
) -> str:
    """Find a supported public email shown beside the business name."""
    location = ", ".join(part.strip() for part in address.split(",")[-2:])
    query = (
        f'"{business_name}" "{location}" '
        "(gmail.com OR hotmail.com OR hotmail.pt OR outlook.com OR outlook.pt OR sapo.pt)"
    )
    rss = fetch_search(query)
    if not rss:
        return ""

    try:
        root = ET.fromstring(rss)
    except ET.ParseError:
        return ""

    normalized_name = re.sub(r"\W+", " ", business_name.casefold()).strip()
    name_words = {word for word in normalized_name.split() if len(word) >= 4}
    for item in root.findall(".//item"):
        result_text = " ".join(
            (
                item.findtext("title", default=""),
                item.findtext("description", default=""),
            )
        )
        normalized_result = re.sub(r"\W+", " ", result_text.casefold())
        if name_words and not name_words.intersection(normalized_result.split()):
            continue
        match = EMAIL_PATTERN.search(result_text)
        if match:
            return match.group(0).lower()

    return ""
