import os
import unittest
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src import cache, fixtures
from src.__main__ import add_public_emails, collect_leads
from src.config import load_dotenv
from src.email_search import find_public_email
from src.http import fetch
from src.places import classify_website, search_without_website
from src.report import summarize, write_report


class ConfigTests(unittest.TestCase):
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


class PlacesTests(unittest.TestCase):
    def test_classify_website_no_website(self) -> None:
        self.assertEqual(classify_website(""), (True, "no_website"))

    def test_classify_website_social_only(self) -> None:
        self.assertEqual(
            classify_website("https://www.facebook.com/examplebiz"),
            (True, "social_only"),
        )
        self.assertEqual(
            classify_website("https://mybiz.business.site"),
            (True, "social_only"),
        )

    def test_classify_website_real_site(self) -> None:
        self.assertEqual(classify_website("https://example.com"), (False, ""))

    def test_filters_businesses_with_real_websites(self) -> None:
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
                        "id": "social-only",
                        "displayName": {"text": "Social Only Biz"},
                        "formattedAddress": "Porto, Portugal",
                        "nationalPhoneNumber": "220 000 001",
                        "googleMapsUri": "https://maps.google.com/social",
                        "websiteUri": "https://www.facebook.com/socialonlybiz",
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

        self.assertEqual(
            [lead["name"] for lead in leads], ["Example Psychology", "Social Only Biz"]
        )
        by_name = {lead["name"]: lead for lead in leads}
        self.assertEqual(by_name["Example Psychology"]["website_gap_reason"], "no_website")
        self.assertEqual(by_name["Social Only Biz"]["website_gap_reason"], "social_only")
        self.assertEqual(
            by_name["Social Only Biz"]["social_url"], "https://www.facebook.com/socialonlybiz"
        )


class EmailSearchTests(unittest.TestCase):
    def test_matches_business_domain_email_with_high_confidence(self) -> None:
        rss = """<rss><channel><item>
        <title>Example Psychology Porto</title>
        <description>Contact geral@examplepsychology.pt for appointments</description>
        </item></channel></rss>"""

        match = find_public_email(
            "Example Psychology",
            "Porto, Portugal",
            lambda _query: rss,
        )

        self.assertEqual(match.email, "geral@examplepsychology.pt")
        self.assertEqual(match.confidence, "business_domain")
        self.assertTrue(match)

    def test_matches_free_mail_when_no_business_domain_found(self) -> None:
        rss = """<rss><channel><item>
        <title>Example Psychology Porto</title>
        <description>Contact example@sapo.pt</description>
        </item></channel></rss>"""

        match = find_public_email(
            "Example Psychology",
            "Porto, Portugal",
            lambda _query: rss,
        )

        self.assertEqual(match.email, "example@sapo.pt")
        self.assertEqual(match.confidence, "free_mail")

    def test_ignores_blocked_placeholder_domains(self) -> None:
        rss = """<rss><channel><item>
        <title>Example Psychology Porto</title>
        <description>Built with Wix, contact support@wixpress.com</description>
        </item></channel></rss>"""

        match = find_public_email(
            "Example Psychology",
            "Porto, Portugal",
            lambda _query: rss,
        )

        self.assertFalse(match)
        self.assertEqual(match.email, "")

    def test_returns_empty_match_when_search_fails(self) -> None:
        match = find_public_email("Example Psychology", "Porto, Portugal", lambda _query: "")
        self.assertFalse(match)


class HttpTests(unittest.TestCase):
    def test_retries_on_retryable_status_then_succeeds(self) -> None:
        attempts = {"count": 0}

        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        def fake_urlopen(_request: object, timeout: int = 20) -> FakeResponse:
            attempts["count"] += 1
            if attempts["count"] < 2:
                error_args: Any = ("http://x", 503, "busy", {}, None)
                raise urllib.error.HTTPError(*error_args)
            return FakeResponse()

        import urllib.request as urllib_request

        original = urllib_request.urlopen
        urllib_request.urlopen = fake_urlopen  # type: ignore[assignment]
        try:
            result = fetch(
                lambda: urllib_request.Request("http://example.test"),
                attempts=3,
                timeout=1,
                backoff_base=0.01,
            )
        finally:
            urllib_request.urlopen = original

        self.assertEqual(result, b"ok")
        self.assertEqual(attempts["count"], 2)

    def test_raises_immediately_on_non_retryable_status(self) -> None:
        def fake_urlopen(_request: object, timeout: int = 20) -> None:
            error_args: Any = ("http://x", 404, "not found", {}, None)
            raise urllib.error.HTTPError(*error_args)

        import urllib.request as urllib_request

        original = urllib_request.urlopen
        urllib_request.urlopen = fake_urlopen  # type: ignore[assignment]
        try:
            with self.assertRaises(urllib.error.HTTPError):
                fetch(
                    lambda: urllib_request.Request("http://example.test"),
                    attempts=3,
                    timeout=1,
                    backoff_base=0.01,
                )
        finally:
            urllib_request.urlopen = original


class ReportTests(unittest.TestCase):
    def _lead(self) -> dict[str, str]:
        return {
            "name": "Example Psychology",
            "email": "example@sapo.pt",
            "email_confidence": "free_mail",
            "email_source": "free_mail",
            "phone": "220 000 000",
            "google_maps_url": "https://maps.google.com/example",
            "website_gap_reason": "no_website",
            "social_url": "",
            "address": "Porto, Portugal",
        }

    def test_writes_text_report(self) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "leads.txt"
            write_report(report, [self._lead()])
            content = report.read_text(encoding="utf-8")
            self.assertIn("name: Example Psychology", content)
            self.assertIn("website_gap: no website", content)

    def test_writes_csv_report(self) -> None:
        with TemporaryDirectory() as directory:
            report = Path(directory) / "leads.csv"
            write_report(report, [self._lead()])
            content = report.read_text(encoding="utf-8")
            self.assertIn("name,category,email", content)
            self.assertIn("Example Psychology", content)

    def test_summarize(self) -> None:
        summary = summarize([self._lead()])
        self.assertIn("Leads: 1", summary)
        self.assertIn("With public email: 1 (100%)", summary)


class CacheTests(unittest.TestCase):
    def _lead(self) -> dict[str, str]:
        return {
            "place_id": "abc123",
            "name": "Example Psychology",
            "category": "psychologist",
            "address": "Porto, Portugal",
            "phone": "220 000 000",
            "google_maps_url": "https://maps.google.com/example",
            "website_gap_reason": "no_website",
            "social_url": "",
            "search_query": "psychologists",
        }

    def test_upsert_and_export(self) -> None:
        with TemporaryDirectory() as directory:
            conn = cache.connect(Path(directory) / "cache.db")
            cache.upsert_lead(conn, self._lead())
            rows = cache.export_all(conn)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Example Psychology")

    def test_record_and_read_email_check(self) -> None:
        with TemporaryDirectory() as directory:
            conn = cache.connect(Path(directory) / "cache.db")
            cache.upsert_lead(conn, self._lead())
            cache.record_email_check(
                conn, "abc123", "geral@example.pt", "business_domain", "directory"
            )
            row = cache.get_email_check(conn, "abc123")
            assert row is not None
            self.assertEqual(row["email"], "geral@example.pt")
            self.assertTrue(cache.is_email_check_fresh(row, refresh_days=30))

    def test_stale_email_check_is_not_fresh(self) -> None:
        with TemporaryDirectory() as directory:
            conn = cache.connect(Path(directory) / "cache.db")
            cache.upsert_lead(conn, self._lead())
            conn.execute(
                "UPDATE leads SET last_checked = '2000-01-01T00:00:00+00:00' WHERE place_id = ?",
                ("abc123",),
            )
            conn.commit()
            row = cache.get_email_check(conn, "abc123")
            self.assertFalse(cache.is_email_check_fresh(row, refresh_days=30))

    def test_missing_email_check_is_not_fresh(self) -> None:
        self.assertFalse(cache.is_email_check_fresh(None, refresh_days=30))


class DryRunTests(unittest.TestCase):
    def test_full_pipeline_runs_on_sample_data_without_network(self) -> None:
        leads = collect_leads(
            "dry-run", "Porto, Portugal", ["dentists"], 20, fixtures.fetch_page
        )
        # The sample business with a real website must be filtered out.
        self.assertEqual(len(leads), 3)

        with TemporaryDirectory() as directory:
            conn = cache.connect(Path(directory) / "cache.db")
            for lead in leads:
                cache.upsert_lead(conn, lead)

            add_public_emails(
                leads,
                conn,
                refresh_emails=False,
                refresh_days=30,
                fetch_search=fixtures.fetch_search,
            )

        by_name = {lead["name"]: lead for lead in leads}
        self.assertEqual(
            by_name["Clinica Dentaria Sorriso"]["email_confidence"], "business_domain"
        )
        self.assertEqual(by_name["Oficina do Zé"]["website_gap_reason"], "social_only")
        self.assertEqual(by_name["Cabeleireiro Beleza Pura"]["email"], "")


if __name__ == "__main__":
    unittest.main()
