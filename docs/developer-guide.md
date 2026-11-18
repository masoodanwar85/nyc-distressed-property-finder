# Developer guide

## Requirements

Python 3.11 or newer, Docker (for local Postgres), git.

## First-time setup

```bash
cd nyc-distressed-property-finder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d
python manage.py migrate
python manage.py createsuperuser
```

Edit `.env` and set `TARGET_ZIP_CODES`. Get a free app token from your NYC Open Data profile (Developer Settings) and set `SOCRATA_APP_TOKEN`.

## Settings (`.env`)

| Variable | Meaning | Default |
| --- | --- | --- |
| `SECRET_KEY` | Django secret | dev value; change in production |
| `DEBUG` | `1` or `0` | `1` |
| `ALLOWED_HOSTS` | comma-separated hosts | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | production origin, with scheme | empty |
| `DATABASE_URL` | database connection | local Postgres from docker compose |
| `SOCRATA_APP_TOKEN` | NYC Open Data token | empty |
| `TARGET_ZIP_CODES` | zip codes to scan | empty |
| `CLASS_B_LIST_FILE` | path to the OSE list | empty |
| `MAX_CLASS_A_UNITS`, `MIN_CLASS_B_UNITS`, `MAX_CLASS_B_UNITS` | candidate rule | 1, 1, 15 |

## Architecture

```
Management command  ->  pipeline.run_pipeline  ->  loaders.*  ->  SocrataClient  ->  NYC Open Data
                                                       |
                                                       v
Web views  <-------------------------------------  Building / Note / Run (Postgres)
```

- **`services/socrata.py`**: `SocrataClient.fetch_all(dataset_id, where, select)` yields rows, paging by 5,000 and ordering by `:id`. `in_clause` and `chunked` build batched queries.
- **`services/loaders.py`**: one function per source. Each takes the client, queries in batches of 50 identifiers, and updates only its own columns. `summarize_charges` and `latest_lien_by_bbl` are pure functions that hold the data rules.
- **`services/classb.py`**: spreadsheet reader for the Class B list.
- **`services/scoring.py`**: `score_building(...)` returns `(score, reasons)`. No database access.
- **`services/pipeline.py`**: orders the steps, records a `Run`, re-raises errors.
- **`views.py`**: `filtered_buildings(params)` is shared by the list and the CSV export.

## Testing

```bash
python manage.py test leads
python manage.py test leads.tests.test_scoring        # one module
DATABASE_URL=sqlite:///test.sqlite3 python manage.py test leads   # without Postgres
```

| File | Covers |
| --- | --- |
| `test_scoring.py` | every scoring rule |
| `test_socrata.py` | paging, token header, query helpers, BBL helpers |
| `test_loaders.py` | each loader, tax and lien rules, Class B parsing |
| `test_pipeline.py` | spreadsheet reading, full run, failure handling |
| `test_commands.py` | both management commands |
| `test_views.py` | login, filters, CSV, notes, status |

Tests never call the network. `leads/tests/fakes.py` provides `FakeClient`, which returns canned rows per dataset ID and records the queries it received.

Write the test first and see it fail before writing code.

## Common tasks

### Change scoring weights

Edit the constants at the top of `leads/services/scoring.py`, update `test_scoring.py` and the table in `docs/specs.md`, then run `python manage.py load_class_b_list` or `run_pipeline` to rescore.

### Add a data source

1. Read a live row and record the fields in `docs/data-sources.md`.
2. Add fields to `Building` and run `python manage.py makemigrations leads`.
3. Write loader tests with `FakeClient`, then the loader in `loaders.py`.
4. Add the step to `pipeline.py` and its count to the run summary.
5. Add a scoring rule if it is a signal, and show the field in the templates and CSV.

### Add a filter to the lead list

Add it to `filtered_buildings` in `views.py` (so the CSV export gets it too), add the form control in `lead_list.html`, and add a test in `test_views.py`.

### Debug a wrong number

1. Find the building's BBL or `hpd_building_id` on its page.
2. Query the dataset directly, for example `.../resource/scjx-j6np.json?parid=<BBL>`.
3. Compare with the rule in `docs/data-sources.md`.
4. Reproduce with a test using those rows before changing the code.

## Database access

GUI clients connect with host `localhost`, port `5432`, database, user and password `nycleads`. App tables: `leads_building`, `leads_note`, `leads_run`.

## Conventions

- Business logic in `leads/services/`; commands and views stay thin.
- Loaders are idempotent: running twice gives the same result.
- User-entered data (`status`, notes) is never overwritten by loaders.
- No Postgres-only features unless the tests are changed to require Postgres.
- Update `.env.example` and this guide when adding a setting.
