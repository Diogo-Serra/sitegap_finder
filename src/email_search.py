"""Public email discovery from indexed search results.

Runs a small set of targeted Bing queries per business (local directories,
common free-mail providers, and a generic contact query), extracts every
candidate email from the results, and scores each candidate so that an
email hosted on the business's own domain outranks a coincidental free-mail
match found in an unrelated search result.
"""

import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

from src.http import fetch, random_user_agent

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.bing.com/search"
FetchSearch = Callable[[str], str]

GENERIC_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "hotmail.com",
        "hotmail.pt",
        "outlook.com",
        "outlook.pt",
        "live.com",
        "live.com.pt",
        "sapo.pt",
        "iol.pt",
        "netcabo.pt",
        "yahoo.com",
        "yahoo.co.uk",
        "icloud.com",
        "protonmail.com",
        "proton.me",
        "zohomail.com",
        "mail.com",
        "uol.com.br",
        "bol.com.br",
    }
)

# Domains that surface real-looking emails which do not belong to the
# business itself: template/CMS placeholders, monitoring tools, and example
# addresses used in documentation.
BLOCKED_DOMAINS = frozenset(
    {
        "example.com",
        "test.com",
        "sentry.io",
        "wixpress.com",
        "schema.org",
        "godaddy.com",
        "domainprivacygroup.com",
        "whoisguard.com",
        "w3.org",
        "wordpress.org",
    }
)

# Local-parts that are almost never a useful business contact even when the
# domain itself is legitimate (mailing-list and automation addresses).
BLOCKED_LOCAL_PREFIXES = ("noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster")

# Public directories that reliably print an email next to the business name;
# searching these first tends to surface high-confidence, low-noise matches.
DIRECTORY_SITES = ("pai.pt", "cylex.pt", "europages.pt", "trustoo.pt")


@dataclass
class EmailMatch:
    """Result of a public email search for one business."""

    email: str = ""
    confidence: str = ""  # "business_domain" | "free_mail" | "other" | ""
    source: str = ""  # "directory" | "free_mail" | "generic" | ""

    def __bool__(self) -> bool:
        return bool(self.email)


def request_search(query: str) -> str:
    """Fetch a Bing RSS results page for a search query, with retries."""
    params = urllib.parse.urlencode({"q": query, "format": "rss", "count": 10})

    def build_request() -> urllib.request.Request:
        return urllib.request.Request(
            f"{SEARCH_URL}?{params}",
            headers={"User-Agent": random_user_agent()},
        )

    try:
        data = fetch(build_request, attempts=3, timeout=20)
        result: str = data.decode("utf-8", errors="replace")
        return result
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        logger.debug("Search request failed for %r: %s", query, error)
        return ""


def _relevant_result_text(rss: str, name_words: set[str]) -> list[str]:
    """Return result snippets that mention the business name, from an RSS feed."""
    try:
        root = ET.fromstring(rss)
    except ET.ParseError:
        return []

    matches = []
    for item in root.findall(".//item"):
        text = " ".join(
            (item.findtext("title", default=""), item.findtext("description", default=""))
        )
        normalized = re.sub(r"\W+", " ", text.casefold())
        if name_words and not name_words.intersection(normalized.split()):
            continue
        matches.append(text)
    return matches


def _score_email(email: str, name_words: set[str]) -> str:
    """Return a confidence tier for a candidate email, or "" to reject it."""
    local_part, _, domain = email.lower().partition("@")
    if not domain or domain in BLOCKED_DOMAINS:
        return ""
    if any(local_part.startswith(prefix) for prefix in BLOCKED_LOCAL_PREFIXES):
        return ""

    if domain in FREE_MAIL_DOMAINS:
        return "free_mail"

    domain_root = domain.split(".")[0]
    for word in name_words:
        if word in domain_root or domain_root in word:
            return "business_domain"

    return "other"


_CONFIDENCE_RANK = {"business_domain": 3, "free_mail": 2, "other": 1, "": 0}


def _best_candidate(texts: list[str], name_words: set[str]) -> EmailMatch:
    """Pick the highest-confidence email found across a batch of result texts."""
    best = EmailMatch()
    for text in texts:
        for raw_email in GENERIC_EMAIL_PATTERN.findall(text):
            confidence = _score_email(raw_email, name_words)
            if not confidence:
                continue
            if _CONFIDENCE_RANK[confidence] > _CONFIDENCE_RANK[best.confidence]:
                best = EmailMatch(email=raw_email.lower(), confidence=confidence)
    return best


def find_public_email(
    business_name: str,
    address: str,
    fetch_search: FetchSearch = request_search,
) -> EmailMatch:
    """Find the highest-confidence public email for a business.

    Tries a directory-targeted query, a free-mail-provider query, and a
    generic contact query, in that order, stopping early only once a
    business-domain-confidence match is found.
    """
    location = ", ".join(part.strip() for part in address.split(",")[-2:])
    normalized_name = re.sub(r"\W+", " ", business_name.casefold()).strip()
    name_words = {word for word in normalized_name.split() if len(word) >= 4}

    site_filter = " OR ".join(f"site:{site}" for site in DIRECTORY_SITES)
    queries = (
        ("directory", f'"{business_name}" "{location}" ({site_filter})'),
        (
            "free_mail",
            f'"{business_name}" "{location}" '
            "(gmail.com OR hotmail.com OR hotmail.pt OR outlook.com OR outlook.pt "
            "OR live.com OR sapo.pt OR yahoo.com)",
        ),
        ("generic", f'"{business_name}" "{location}" (email OR contacto OR contactos)'),
    )

    best = EmailMatch()
    for source, query in queries:
        rss = fetch_search(query)
        if not rss:
            continue
        texts = _relevant_result_text(rss, name_words)
        candidate = _best_candidate(texts, name_words)
        if _CONFIDENCE_RANK[candidate.confidence] > _CONFIDENCE_RANK[best.confidence]:
            best = EmailMatch(email=candidate.email, confidence=candidate.confidence, source=source)
        if best.confidence == "business_domain":
            break

    return best
