"""Shared HTTP helpers: retry with backoff and user-agent rotation."""

import logging
import random
import time
import urllib.error
import urllib.request
from typing import Callable

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}

USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
)


def random_user_agent() -> str:
    """Return a plausible desktop browser User-Agent string."""
    return random.choice(USER_AGENTS)


def fetch(
    request_factory: Callable[[], urllib.request.Request],
    *,
    attempts: int = 3,
    timeout: int = 20,
    backoff_base: float = 1.5,
) -> bytes:
    """Perform a request with exponential backoff, jitter, and UA rotation.

    ``request_factory`` is called fresh on every attempt so headers (such as
    the User-Agent) can be rotated. Retries only on connection issues and on
    retryable HTTP status codes; any other HTTP error is raised immediately.
    """
    last_error: Exception = RuntimeError("no attempt was made")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request_factory(), timeout=timeout) as response:
                data: bytes = response.read()
                return data
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in RETRYABLE_STATUS_CODES or attempt == attempts - 1:
                raise
            logger.debug("HTTP %s on attempt %d, retrying", error.code, attempt + 1)
        except urllib.error.URLError as error:
            last_error = error
            if attempt == attempts - 1:
                raise
            logger.debug("Network error on attempt %d: %s, retrying", attempt + 1, error)

        time.sleep(backoff_base * (2**attempt) + random.uniform(0, 0.5))

    raise last_error
