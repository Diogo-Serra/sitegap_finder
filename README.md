# SiteGap Finder

SiteGap finds local businesses that do not have a website listed on Google Places. It exports their public contact details so web developers can identify potential clients.

## How it works

1. Searches Google Places for a category and location.
2. Removes every business that already has a website listed.
3. Searches public results for a matching Gmail, Hotmail, Outlook, Live, or Sapo email.
4. Saves the business name, email, phone number, and Google Maps link.

Email addresses are never guessed. If no reliable public email is found, the field stays empty.

## Requirements

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/)
- A Google Cloud API key with **Places API (New)** enabled

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

## Output

Results are saved to `leads.txt` by default:

```text
name: Example Psychology
email: example@sapo.pt
phone: +351 220 000 000
google_maps: https://maps.google.com/...
```

## Commands

```bash
make install  # Create the environment and install dependencies
make run      # Run SiteGap
make test     # Run offline tests
make lint     # Check code style and types
make clean    # Remove generated Python files
```

## Project structure

```text
src/
├── __main__.py      # Command-line workflow
├── config.py        # Defaults and .env loading
├── places.py        # Google Places search and filtering
├── email_search.py  # Public email matching
└── report.py        # Text report generation
tests/               # Offline unit tests
```

## Responsible use

Google Places requests may incur charges. Verify results before contacting a business and follow applicable privacy, marketing, and anti-spam laws.