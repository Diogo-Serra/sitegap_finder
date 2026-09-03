# SiteGap Finder

SiteGap finds local businesses that have no real website — whether Google Places lists no website at all, or only a Facebook/Instagram page — and exports their public contact details so web developers can identify potential clients.

## How it works

1. Searches Google Places for a category and location.
2. Removes every business that has a real website, but **keeps** businesses whose only "website" is a social media page (Facebook, Instagram, Linktree, WhatsApp, or a free `business.site` page) — these are prime leads.
3. Searches public results across multiple targeted queries (business directories, common free-mail providers, and generic contact pages) for a public email, and scores each candidate so an email on the business's own domain outranks a coincidental free-mail match.
4. Caches results in a local SQLite database so re-running a search skips businesses that were already checked recently, and builds a growing lead list over time.
5. Saves the business name, email (with a confidence tier), phone number, Google Maps link, and website-gap reason to a report.

Email addresses are never guessed. If no reliable public email is found, the field stays empty.

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- A Google Cloud API key with **Places API (New)** enabled

No third-party Python dependencies are required — everything runs on the standard library.

## Installation

```bash
git clone git@github.com:Diogo-Serra/sitegap_finder.git
cd sitegap_finder
make install
cp .env.example .env
```

Open `.env` and add your key:

```dotenv
GOOGLE_PLACES_API_KEY="your-api-key"
```

That's the only manual step required. Everything else is ready to run.

## Usage

Run the default example:

```bash
make run
```

Choose a location, categories, result limit, and output file:

```bash
make run ARGS='"Porto, Portugal" psychologists plumbers "car repair" --limit 30 --output porto-leads.txt'
```

Categories are normal search text, not a predefined list. Examples include `dentists`, `restaurants`, `accountants`, `hairdressers`, or any profession understood by Google Places.

You can also run the CLI directly:

```bash
uv run sitegap "Lisbon, Portugal" dentists electricians --limit 20
```

Start with a small `--limit` (for example `5`) on your first run to confirm results look right and check your Google Cloud billing dashboard before scaling up.

### Useful flags

| Flag | Purpose |
| --- | --- |
| `--output FILE` | Report path. Use a `.csv` extension for a spreadsheet-ready export, otherwise a plain-text report is written. |
| `--cache-db FILE` | SQLite database used to remember leads and email results across runs (default `sitegap_cache.db`). |
| `--no-cache` | Disable the cache entirely. |
| `--refresh-emails` | Force a fresh email lookup even if a cached result exists. |
| `--refresh-days N` | How long a cached email lookup stays valid before it's rechecked (default 30). |
| `--export-cache FILE` | Dump every lead ever cached to a CSV file and exit, without searching. |
| `--no-email-search` | Skip email lookups entirely; only list businesses without a real website. |
| `-v`, `--verbose` | Show debug logging, including retry attempts and search failures. |

## Output

### Text report (default)

```text
name: Example Psychology
email: example@sapo.pt
email_confidence: free_mail
phone: +351 220 000 000
google_maps: https://maps.google.com/...
website_gap: no website
```

### CSV report (`--output leads.csv`)

A spreadsheet-ready file with columns: `name, category, email, email_confidence, email_source, phone, google_maps_url, website_gap_reason, social_url, address`.

### Email confidence tiers

- `business_domain` — the email's domain matches the business name (highest confidence, most actionable).
- `free_mail` — a Gmail/Hotmail/Outlook/Sapo/Yahoo/etc. address associated with the business.
- `other` — a plausible but unverified match; review before contacting.

### Website gap reasons

- `no_website` — Google Places lists no website at all.
- `social_only` — the only "website" on file is a Facebook/Instagram page or a free auto-generated page.

## Commands

```bash
make install  # Create the environment and install dependencies
make run      # Run SiteGap
make lint     # Check code style and types
make clean    # Remove generated Python files
```

## Project structure

```text
src/
├── __main__.py       # Command-line workflow
├── config.py         # Defaults and .env loading
├── http.py           # Shared retry/backoff and user-agent rotation
├── places.py         # Google Places search, filtering, and website-gap detection
├── email_search.py   # Public email discovery and confidence scoring
├── cache.py          # SQLite persistence across runs
└── report.py         # Text/CSV report generation and run summaries
```

## Responsible use

Google Places requests may incur charges. Verify results before contacting a business and follow applicable privacy, marketing, and anti-spam laws.
