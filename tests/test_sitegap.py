import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.config import load_dotenv
from src.email_search import find_public_email
from src.places import search_without_website
from src.report import write_report


class SiteGapTests(unittest.TestCase):
    def test_loads_dotenv(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("GOOGLE_PLACES_API_KEY='test-key'\n", encoding="utf-8")
            previous = os.environ.pop("GOOGLE_PLACES_API_KEY", None)
            try:
                load_dotenv(path)
                self.assertEqual(os.environ["GOOGLE_PLACES_API_KEY"], "test-key")
            finally:
                os.environ.pop("GOOGLE_PLACES_API_KEY", None)
                if previous:
                    os.environ["GOOGLE_PLACES_API_KEY"] = previous

    def test_filters_businesses_with_websites(self) -> None:
        def fake_fetch(_key: str, _payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "places": [
                    {
                        "id": "no-site",
                        "displayName": {"text": "Example Psychology"},
                        "formattedAddress": "Porto, Portugal",
                        "nationalPhoneNumber": "220 000 000",
                        "googleMapsUri": "https://maps.google.com/example",
                    },
                    {
                        "id": "has-site",
                        "displayName": {"text": "Has Website"},
                        "websiteUri": "https://example.com",
                    },
                ]
            }

        leads = search_without_website(
            "test-key", "psychologists", "Porto, Portugal", 20, fake_fetch
        )

        self.assertEqual([lead["name"] for lead in leads], ["Example Psychology"])

    def test_matches_public_email_to_business(self) -> None:
        rss = """<rss><channel><item>
        <title>Example Psychology Porto</title>
        <description>Contact example@sapo.pt</description>
        </item></channel></rss>"""

        email = find_public_email(
            "Example Psychology",
            "Porto, Portugal",
            lambda _query: rss,
        )

        self.assertEqual(email, "example@sapo.pt")

    def test_writes_report(self) -> None:
        lead = {
            "name": "Example Psychology",
            "email": "example@sapo.pt",
            "phone": "220 000 000",
            "google_maps_url": "https://maps.google.com/example",
        }
        with TemporaryDirectory() as directory:
            report = Path(directory) / "leads.txt"
            write_report(report, [lead])
            self.assertIn("name: Example Psychology", report.read_text(encoding="utf-8"))
