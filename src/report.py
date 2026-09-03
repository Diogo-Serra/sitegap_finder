"""Lead report output."""

import csv
from pathlib import Path

from src.places import Lead

REPORT_FIELDS = (
    "name",
    "category",
    "email",
    "email_confidence",
    "email_source",
    "phone",
    "google_maps_url",
    "website_gap_reason",
    "social_url",
    "address",
)

GAP_REASON_LABELS = {
    "no_website": "no website",
    "social_only": "social media page only",
}


def write_report(path: Path, leads: list[Lead]) -> None:
    """Write leads to ``path``, using CSV format for a ``.csv`` extension."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        _write_csv(path, leads)
    else:
        _write_text(path, leads)


def _write_text(path: Path, leads: list[Lead]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for lead in leads:
            output.write(f'name: {lead.get("name", "")}\n')
            output.write(f'email: {lead.get("email", "")}\n')
            if lead.get("email"):
                output.write(f'email_confidence: {lead.get("email_confidence", "")}\n')
            output.write(f'phone: {lead.get("phone", "")}\n')
            output.write(f'google_maps: {lead.get("google_maps_url", "")}\n')
            gap_reason = lead.get("website_gap_reason", "")
            output.write(f'website_gap: {GAP_REASON_LABELS.get(gap_reason, gap_reason)}\n')
            if lead.get("social_url"):
                output.write(f'social_url: {lead["social_url"]}\n')
            output.write("\n")


def _write_csv(path: Path, leads: list[Lead]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow({field: lead.get(field, "") for field in REPORT_FIELDS})


def summarize(leads: list[Lead]) -> str:
    """Return a short human-readable summary of a batch of leads."""
    total = len(leads)
    with_email = sum(1 for lead in leads if lead.get("email"))
    social_only = sum(1 for lead in leads if lead.get("website_gap_reason") == "social_only")
    confidence_counts: dict[str, int] = {}
    for lead in leads:
        confidence = lead.get("email_confidence", "")
        if confidence:
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

    lines = [
        f"Leads: {total}",
        f"With public email: {with_email} ({_percent(with_email, total)})",
        f"No website at all: {total - social_only}",
        f"Social media page only: {social_only}",
    ]
    for confidence in ("business_domain", "free_mail", "other"):
        count = confidence_counts.get(confidence, 0)
        if count:
            lines.append(f"  - {confidence}: {count}")
    return "\n".join(lines)


def _percent(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{100 * part / total:.0f}%"
