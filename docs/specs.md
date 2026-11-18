# Software specification

Version 1: lead list. Last updated 2026-11-16.

## Purpose

Give a New York City property buyer a ranked weekly list of small, legally transient-use buildings whose owners show signs of financial distress, so he can approach owners before the property reaches the open market.

## Users

| User | Does |
| --- | --- |
| Client (buyer) | Reviews the list, opens buildings, sets status, writes notes, exports CSV |
| Operator (developer) | Configures zip codes, runs or schedules the pipeline, loads the Class B list, checks data |

## Functional requirements

### Candidate filter

- F1. A building is a candidate when HPD records show Class A units <= 1 and Class B units between 1 and 15, its record status is Active, and its zip code is in the configured list.
- F2. The three limits are settings (`MAX_CLASS_A_UNITS`, `MIN_CLASS_B_UNITS`, `MAX_CLASS_B_UNITS`).
- F3. A missing Class A count is treated as 0.

### Legal-use confirmation

- F4. A candidate found on the Office of Special Enforcement Class B Multiple Dwellings List, by BIN or BBL, is marked "Listed". All others are "Unverified".
- F5. An empty or unreadable list file must not clear existing flags.

### Distress signals

- F6. Tax owed: sum of open balances already due, per tax lot, with the number of unpaid billing periods and the data date.
- F7. Lien list: the most recent Tax Lien Sale List entry for the lot, with stage, month and whether it was for water debt only.
- F8. Registration: HPD registration end date, registered owner and managing agent.

### Scoring

- F9. Score is a sum of points; every point has a plain-language reason shown to the user.

| Signal | Points |
| --- | --- |
| On city Class B list | 30 |
| Tax owed under $5,000 | 5 |
| Tax owed $5,000 to $19,999 | 20 |
| Tax owed $20,000 or more | 35 |
| 4 or more unpaid billing periods | 10 |
| On a lien list | 25 |
| On a lien list, water debt only | 10 |
| HPD registration lapsed | 5 |

Weights are constants in `leads/services/scoring.py` and are expected to change after client feedback.

### Web application

- F10. Every page requires login.
- F11. Lead list: sorted by score, then tax owed; filters for zip code, Class B list, minimum tax owed and status; 50 rows per page.
- F12. Building page: identifiers, units, signals, reasons, owner, links to DOB certificate records and HPD Online historical records.
- F13. Status per building: New, Reviewing, Contacted, In negotiation, Rejected. Status and notes survive data reloads.
- F14. CSV export of the current filtered list.
- F15. Run history: date, result, candidate count, new candidates, error text.
- F16. Django admin for staff users.

### Pipeline

- F17. One command runs all steps in order and records a `Run`.
- F18. A failed run is recorded with its error and exits non-zero.
- F19. Reloading updates existing buildings; it never duplicates them.

## Non-functional requirements

- N1. Data is taken from the NYC Open Data API with queries filtered by zip code, BBL or ID. No whole-dataset downloads in version 1.
- N2. No proxies and no bypassing of site blocks or rate limits.
- N3. Tests run without network access.
- N4. Postgres in development and production.
- N5. Secrets only in `.env`.

## Data model

| Model | Key fields |
| --- | --- |
| `Building` | `hpd_building_id` (unique), `bin`, `bbl`, address parts, `class_a_units`, `class_b_units`, `on_class_b_list`, `tax_owed`, `unpaid_periods`, `tax_as_of`, `lien_stage`, `lien_month`, `lien_water_only`, `owner_name`, `agent_name`, `registration_end`, `score`, `score_reasons`, `status`, `first_seen`, `last_seen` |
| `Note` | `building`, `author`, `text`, `created` |
| `Run` | `started`, `finished`, `ok`, `summary` (JSON), `error` |

## Out of scope for version 1

- Reading certificates of occupancy or I-cards.
- Foreclosure (lis pendens) filings.
- Citywide coverage.
- Email or chat alerts.
- Owner contact enrichment beyond HPD registration names.

## Roadmap

1. Validate tax-owed logic and owner fields against live data.
2. Certificate of occupancy and I-card retrieval for the top-ranked buildings, with a human review queue and verification levels `listed`, `documented`, `conflict`, `unverified`.
3. Lien-list monitoring when the 2027 notice list is published.
4. Foreclosure filings from a licensed feed or manual checks.
5. Weekly email of new and changed leads.
6. Citywide loads.

## Limits and disclaimer

The software produces leads for human review. It does not determine legal occupancy or title. Confirm both with an attorney before making an offer.
