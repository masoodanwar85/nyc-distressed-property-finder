# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Codex, Copilot) working in this repository. Humans: start with `README.md` and `docs/developer-guide.md`.

## What this project is

A Django app that finds NYC buildings with 0-1 Class A units and 1-15 Class B units, attaches distress signals (tax owed, lien lists, lapsed registration), scores them, and shows a ranked lead list. Data comes from NYC Open Data (Socrata API). Full context: `docs/specs.md`.

## Commands

```bash
source .venv/bin/activate
docker compose up -d                    # local Postgres
python manage.py migrate
python manage.py test leads             # full test suite, no network needed
python manage.py run_pipeline           # live run against NYC Open Data
python manage.py load_class_b_list --file data/<file>
python manage.py runserver
```

Quick test run without Postgres: `DATABASE_URL=sqlite:///test.sqlite3 python manage.py test leads`.

## Where things are

| Path | Purpose |
| --- | --- |
| `config/settings.py` | All settings; values come from `.env` |
| `leads/models.py` | `Building`, `Note`, `Run` |
| `leads/services/socrata.py` | API client (paging, app token) |
| `leads/services/loaders.py` | One function per data source, plus `score_all` |
| `leads/services/classb.py` | Reads the OSE Class B spreadsheet |
| `leads/services/scoring.py` | Pure scoring function and its weights |
| `leads/services/pipeline.py` | Runs every step and records a `Run` |
| `leads/management/commands/` | Thin CLI wrappers around services |
| `leads/views.py`, `leads/templates/` | Web UI |
| `leads/tests/` | Tests; `fakes.py` holds the fake API client |
| `docs/` | Specs, workflow, code flow (`docs/code-flow.md`), developer guide, deployment |

## Rules

1. **Tests first.** Write a failing test, watch it fail, then write the code. Run the whole suite before finishing.
2. **No network in tests.** Use `FakeClient` from `leads/tests/fakes.py`. Loader functions take the client as an argument for this reason.
3. **Business logic lives in `leads/services/`.** Views and management commands stay thin.
4. **Keep scoring pure.** `score_building` takes plain values and returns `(score, reasons)`; no database access inside it.
5. **Never invent dataset field names.** Read a live row first (`https://data.cityofnewyork.us/resource/<id>.json?$limit=1`) and record the names in `docs/data-sources.md`.
6. **Filter in the API query.** Do not download whole datasets; use `$where` with zip codes, BBLs or IDs, in batches of 50.
7. **Identifiers.** Buildings are keyed on `hpd_building_id`. Unit counts are per building (BIN); tax and lien data are per lot (BBL). Build BBLs with `leads/services/bbl.py`.
8. **Loaders overwrite their own columns only.** Never reset `status` or notes on reload.
9. **Database-neutral code.** Tests run on SQLite and Postgres; avoid Postgres-only features unless the tests are updated to require Postgres.
10. **Model changes need a migration** (`python manage.py makemigrations leads`), committed with the change.
11. **Secrets stay in `.env`**, which is git-ignored. Update `.env.example` when adding a setting.
12. **City websites.** Bulk data comes from the open data API. Per-building page fetches (DOB BIS, HPD Online) are for shortlisted buildings only, one at a time with pauses and caching. Do not add proxy rotation or other ways around a site's blocks or rate limits.
13. **Update the docs** in `docs/` when behaviour, data sources, settings or deployment steps change.

## Known unverified areas

Check these before building on them; details in `docs/data-sources.md`.

- The rule for choosing the current tax balance from the DOF dataset.
- Field names for HPD registrations and contacts.
- Column layout of the OSE Class B spreadsheet.

## Not built yet

Certificate of occupancy and I-card retrieval, foreclosure filings, email alerts. See the roadmap in `docs/specs.md`.

## Domain glossary

- **Class A unit:** permanent residence (ordinary apartment).
- **Class B unit:** transient occupancy (hotel, rooming house, single-room occupancy). Not the same as a Department of Finance building class starting with "B".
- **BIN:** Building Identification Number, 7 digits, one per building.
- **BBL:** Borough-Block-Lot, 10 digits, one per tax lot. A lot can hold several buildings.
- **HPD:** Department of Housing Preservation and Development. **DOB:** Department of Buildings. **DOF:** Department of Finance. **OSE:** Office of Special Enforcement.
- **Lien:** the city's legal claim on a property for unpaid tax or water charges.
- **I-card:** HPD's historical handwritten occupancy record for older buildings.
