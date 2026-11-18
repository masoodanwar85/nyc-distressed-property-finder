# Data sources

All API datasets are read at `https://data.cityofnewyork.us/resource/<ID>.json` with SoQL parameters (`$where`, `$select`, `$limit`, `$offset`, `$order`). Send the app token in the `X-App-Token` header.

"Verified" means the field names were read from live API rows on 2026-11-16.

## Buildings Subject to HPD Jurisdiction (`kj4p-ruqc`) - verified

Used by `load_hpd_buildings`. One row per building.

| Field | Used as |
| --- | --- |
| `buildingid` | `hpd_building_id` (key; also in the HPD Online link) |
| `bin` | BIN (also in the DOB link) |
| `boroid`, `block`, `lot` | BBL |
| `housenumber`, `streetname`, `boro`, `zip` | address |
| `legalclassa`, `legalclassb` | unit counts (numeric; the filter) |
| `dobbuildingclass` | description, for example "HEREAFTER CONVERTED CLASS A" |
| `registrationid` | link to registrations |
| `recordstatus` | filter: `Active` |

Query: `zip in (...) AND legalclassb >= 1 AND legalclassb <= 15 AND (legalclassa <= 1 OR legalclassa IS NULL) AND recordstatus = 'Active'`.

## DOF Property Charges Balance (`scjx-j6np`) - fields verified, logic not

Used by `load_tax_balances`. Many rows per lot: one per billing period and charge, repeated across extracts.

| Field | Used as |
| --- | --- |
| `parid` | BBL |
| `dt_pd_begin` | billing period |
| `code` | charge code (for example `CHG`) |
| `due_date` | only balances already due are counted |
| `sum_bal` | open balance |
| `extractdt`, `up_date` | picks the newest row |

Rule in `summarize_charges`: for each (`parid`, `dt_pd_begin`, `code`) keep the row with the newest `extractdt` (then `up_date`); sum `sum_bal` where it is positive and due; count distinct periods with a balance.

**To verify:** compare 10 lots with https://a836-pts-access.nyc.gov. If totals differ, inspect how extracts overlap and whether other `code` values should be excluded. Other fields seen: `rectype`, `valclass`, `luc`, `trans_ctr`, `prior_owner_flag`, `sum_liab`, `sum_coll`, `sum_int`, `sum_dsc`, `taxyear`, `cycle`, `rolltype`.

## Tax Lien Sale Lists (`9rz4-mjek`) - verified

Used by `load_lien_lists`. One row per lot per notice stage per sale year.

| Field | Used as |
| --- | --- |
| `borough`, `block`, `lot` | BBL |
| `month` | sale cycle date; the latest wins |
| `cycle` | stage, for example "90 Day Notice", "Final Sale" |
| `water_debt_only` | `Y` or `N` |
| `zip_code` | query filter |

No sale was held in 2026. Entries are from 2025 and earlier until the 2027 notice list is published (expected late February or early March 2027).

## Multiple Dwelling Registrations (`tesw-yqqr`) and Registration Contacts (`feu5-w2e2`) - not verified

Used by `load_registrations`. Field names are assumed from the lowercase convention of the other datasets and the nycdb schema.

| Dataset | Fields assumed |
| --- | --- |
| Registrations | `registrationid`, `registrationenddate` |
| Contacts | `registrationid`, `type`, `corporationname`, `firstname`, `lastname` |

Owner is the first of `CorporateOwner`, `IndividualOwner`, `HeadOfficer`; agent is type `Agent`.

**To verify:** open each dataset with `?$limit=1`. If owner names load empty, fix the names in `load_registrations`.

## OSE Class B Multiple Dwellings List (spreadsheet) - layout not verified

Download page: https://www.nyc.gov/site/specialenforcement/reporting-law/class-b-mdl.page

Read by `leads/services/classb.py`, which accepts `.xls`, `.xlsx` or `.csv`, skips title rows, and looks for a BIN column, a BBL column, or borough + block + lot columns.

**To verify:** after `load_class_b_list`, the command prints how many BINs and BBLs it found. Zero means the column names need handling.

## Per-building city pages (links only in version 1)

| Page | URL pattern |
| --- | --- |
| DOB certificates of occupancy | `https://a810-bisweb.nyc.gov/bisweb/COsByLocationServlet?requestid=0&allbin=<BIN>` |
| HPD Online historical records (I-cards) | `https://hpdonline.nyc.gov/hpdonline/building/<buildingid>/historical` |

## Not used

PLUTO (versioned releases, lags), PropStream and StreetEasy (derived data), Who Owns What (built on the same open data).
