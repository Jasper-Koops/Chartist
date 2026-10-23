# Chartist

This application is the backend server for Chartist, a tool designed to analyze and visualize voting patterns of political parties based on their voting records.

## Features
- Import motions, votes and motion texts from the API of the Dutch House of Representatives (Tweede Kamer), kept in sync on every run
- Detect parties that continue under a new name (e.g. GroenLinks-PvdA -> PRO); the successor inherits the votes in the analysis
- Run PCA (Principal Component Analysis) on voting data to identify patterns among political parties
- Calculate a pairwise agreement matrix between parties, overall and per month
- Provide an API to access processed data for frontend visualization
- Test pages for the charts, parties and motions


## Installation

Use Python 3.11 or newer. The commands below use Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies (use requirements/base.txt for production)
pip install -r requirements/dev.txt

# Create the local settings file, then set SECRET_KEY (and DATABASES,
# ALLOWED_HOSTS, DEBUG as needed). Settings refuse to load without it.
cp Chartist/secrets/secrets.example.py Chartist/secrets/local.py

# Generate a value to paste into SECRET_KEY in the local settings file
python -c "from secrets import token_urlsafe; print(token_urlsafe(64))"

# Run migrations
python manage.py migrate

# Load initial data (parties, motions, votes and motion texts)
python manage.py import_data

# Run initial analysis (participation, PCA and agreement matrix)
python manage.py run_analysis

# Create a superuser for admin access
python manage.py createsuperuser
```

## Starting the server:

```bash
python manage.py runserver
```

## Keeping the data up to date

Run the import and the analysis by hand:

```bash
# Sync parties, votes and texts with the API. Every run is recorded as an
# ImportRun (visible in the admin and in /api/v1/status/).
python manage.py import_data

# Re-download every motion text, e.g. after changing the text extraction.
python manage.py import_data --refetch-texts

python manage.py run_analysis
```

Or let Celery do it every night at 00:15: one chained task imports the data
and then runs the analysis after every successful import. This
needs a Redis server on `127.0.0.1:6379` (see `CELERY_BROKER_URL` in
`Chartist/settings.py`; on Ubuntu: `sudo apt install redis-server`) and two
processes next to the Django server:

```bash
# Worker: executes the tasks
celery -A Chartist worker --loglevel=info

# Scheduler: starts the nightly task
celery -A Chartist beat --loglevel=info
```

Motion texts are downloaded when missing or when their publication identifier,
document version, or version modification timestamp changes.
A failed download keeps the previous text and is retried on the next import.

## Party successions and aliases

Successions (a party continuing under a new identity) are detected during the
import. Check or correct them in the admin under *Party successions*; a
detection is never deleted automatically, so a correction is kept.

Aliases are older API ids under which the API still records a party's votes
(e.g. 50PLUS after it was registered again in 2025). They are detected during
the import too, and listed in the admin under *Party aliases*.

## Important urls
- API Root (Interactive): `http://127.0.0.1:8000/api/v1/`
- Data status (last sync, newest vote): `http://127.0.0.1:8000/api/v1/status/`
- Admin Panel: `http://127.0.0.1:8000/admin/`
- Home (landscape, agreement matrix, parties, axes): `http://127.0.0.1:8000/`
- Party page (agreement with every party, timeline): `http://127.0.0.1:8000/party/<id>/`
- Pair view (two parties compared): `http://127.0.0.1:8000/pair/<id>/<other_id>/`
- PCA component (parties and motions behind an axis): `http://127.0.0.1:8000/component/<number>/`
- Motion search: `http://127.0.0.1:8000/motions/`
- Motion page (text, documents, votes): `http://127.0.0.1:8000/motion/<id>/`

## Development

Install the pre-commit hooks once; they run the Django checks and tests,
black, ruff and mypy on every commit:

```bash
pre-commit install
```

Browser regression checks run separately against a temporary test database:

```bash
python -m playwright install chromium
python manage.py test browser_tests.journeys
```

They exercise navigation at phone, tablet and desktop widths, the map controls,
statistics, highlight choices, and the party/comparison/motion/axis journey.
The real chart libraries load from their configured CDNs, so this suite needs
network access. Screenshots are saved in `.browser-artifacts/`.
