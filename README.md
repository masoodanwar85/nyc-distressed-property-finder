# NYC Distressed Property Finder

Finds NYC buildings with 0-1 Class A units and 1-15 Class B units, adds distress
signals (tax owed, lien lists, lapsed registration), ranks them, and shows the
list in a small web app with filters, notes, status tracking and CSV export.

This is version 1 (the lead list). Certificate of occupancy and I-card
retrieval are not built yet; each building page links to those city records.

## Setup

Requires Python 3.11+ and Docker (for Postgres).

```bash
cd nyc-distressed-property-finder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit: zip codes, app token, secret key
docker compose up -d            # starts Postgres on localhost:5432
python manage.py migrate
python manage.py createsuperuser
```

## Run

```bash
python manage.py run_pipeline                  # uses TARGET_ZIP_CODES from .env
python manage.py run_pipeline --zips 10027,10030
python manage.py runserver                     # then open http://127.0.0.1:8000
```

### Class B list

Download the spreadsheet from
https://www.nyc.gov/site/specialenforcement/reporting-law/class-b-mdl.page
and either set `CLASS_B_LIST_FILE` in `.env` or run:

```bash
python manage.py load_class_b_list --file data/class-b-list.xls
```

The reader looks for a BIN column, a BBL column, or borough + block + lot.

### Weekly schedule (cron)

```
0 3 * * 1 cd /path/to/project && .venv/bin/python manage.py run_pipeline >> pipeline.log 2>&1
```

## What the pipeline does

| Step | Source (NYC Open Data ID) | Result |
| --- | --- | --- |
| 1 | Buildings Subject to HPD Jurisdiction (kj4p-ruqc) | Candidate buildings by zip and A/B unit rule |
| 2 | OSE Class B list (spreadsheet) | "On city Class B list" flag |
| 3 | DOF Property Charges Balance (scjx-j6np) | Tax owed, unpaid periods |
| 4 | Tax Lien Sale Lists (9rz4-mjek) | Latest lien stage per lot |
| 5 | HPD Registrations (tesw-yqqr) and Contacts (feu5-w2e2) | Owner, agent, registration end |
| 6 | Scoring (`leads/services/scoring.py`) | Score and reasons |

Scoring weights are constants at the top of `leads/services/scoring.py`.

## Check before trusting the numbers

1. **Tax owed.** The DOF dataset stores several extracts over time. The code
   keeps the newest row per parcel, billing period and charge code, then sums
   open balances that are already due. Compare 10 buildings with the DOF
   property tax site (https://a836-pts-access.nyc.gov) before showing the client.
2. **Registration and contact field names** (`registrationenddate`, `type`,
   `corporationname`, `firstname`, `lastname`) follow the convention of the
   other datasets but were not read from live rows. If owner names come back
   empty, open `https://data.cityofnewyork.us/resource/feu5-w2e2.json?$limit=1`
   and adjust `load_registrations` in `leads/services/loaders.py`.
3. **Class B spreadsheet layout** was not available when this was written. If
   `load_class_b_list` reports 0 BINs and 0 BBLs, check the column names.
4. **Unit counts.** Compare a few buildings with HPD Online.

## Documentation

See `docs/` (specs, workflow, data sources, developer guide, Ubuntu deployment) and `AGENTS.md` for AI coding agents.

## Tests

```bash
python manage.py test leads
```

Tests use fake API responses and need no network. They run against whatever
`DATABASE_URL` points to (Postgres via docker compose, or
`DATABASE_URL=sqlite:///test.sqlite3` for a quick run).

## Layout

```
config/                  Django settings and URLs
leads/models.py          Building, Note, Run
leads/services/          socrata.py (API client), loaders.py, classb.py, scoring.py, pipeline.py
leads/management/commands/   run_pipeline, load_class_b_list
leads/views.py, templates/   lead list, building page, CSV export, run history
leads/tests/             test suite
```

This tool produces leads for review. Confirm legal occupancy and title with an
attorney before making an offer.
