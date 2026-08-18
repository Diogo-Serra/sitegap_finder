"""Lead report output."""

from pathlib import Path

from src.places import Lead


def write_report(path: Path, leads: list[Lead]) -> None:
    """Write leads as easy-to-read text blocks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for lead in leads:
            output.write(f'name: {lead["name"]}\n')
            output.write(f'email: {lead["email"]}\n')
            output.write(f'phone: {lead["phone"]}\n')
            output.write(f'google_maps: {lead["google_maps_url"]}\n\n')
