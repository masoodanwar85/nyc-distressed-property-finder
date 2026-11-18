"""Load each city dataset into the Building table.

Every function takes a SocrataClient so tests can pass a fake one.
Field names below were read from live API rows on 2026-11-16, except the
registration and contact datasets, which follow the same lowercase convention
and should be checked on the first real run.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings

from leads.models import Building
from .bbl import make_bbl
from .scoring import score_building
from .socrata import chunked, in_clause

HPD_BUILDINGS = "kj4p-ruqc"
PROPERTY_CHARGES = "scjx-j6np"
LIEN_LISTS = "9rz4-mjek"
HPD_REGISTRATIONS = "tesw-yqqr"
HPD_CONTACTS = "feu5-w2e2"

BATCH = 50
OWNER_TYPES = ("CorporateOwner", "IndividualOwner", "HeadOfficer")


def _int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _date(value):
    """'2025-06-01T00:00:00.000' -> date(2025, 6, 1); empty -> None."""
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _money(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return Decimal("0")


# --- HPD buildings: the candidate filter -------------------------------------

def load_hpd_buildings(client, zip_codes, max_a=None, min_b=None, max_b=None, today=None):
    """Upsert every active HPD building in the zip codes that meets the A/B unit rule."""
    max_a = settings.MAX_CLASS_A_UNITS if max_a is None else max_a
    min_b = settings.MIN_CLASS_B_UNITS if min_b is None else min_b
    max_b = settings.MAX_CLASS_B_UNITS if max_b is None else max_b
    today = today or date.today()
    where = (
        f"{in_clause('zip', zip_codes)} AND legalclassb >= {min_b} AND legalclassb <= {max_b} "
        f"AND (legalclassa <= {max_a} OR legalclassa IS NULL) AND recordstatus = 'Active'"
    )
    count = 0
    for row in client.fetch_all(HPD_BUILDINGS, where=where):
        building_id = _int(row.get("buildingid"), default=None)
        if building_id is None:
            continue
        values = dict(
            bin=str(row.get("bin") or "")[:7],
            bbl=make_bbl(row.get("boroid"), row.get("block"), row.get("lot")),
            registration_id=_int(row.get("registrationid"), default=None) or None,
            house_number=row.get("housenumber", ""),
            street_name=row.get("streetname", ""),
            borough=row.get("boro", ""),
            zip_code=str(row.get("zip") or "")[:5],
            class_a_units=_int(row.get("legalclassa")),
            class_b_units=_int(row.get("legalclassb")),
            dob_building_class=row.get("dobbuildingclass", ""),
            last_seen=today,
        )
        building, created = Building.objects.update_or_create(hpd_building_id=building_id, defaults=values)
        if created:
            building.first_seen = today
            building.save(update_fields=["first_seen"])
        count += 1
    return count


# --- OSE Class B list -----------------------------------------------------------

def apply_class_b_list(bins, bbls):
    """Flag buildings whose BIN or BBL is on the city's Class B list; clear the rest."""
    bins, bbls = {b for b in bins if b}, {b for b in bbls if b}
    if not bins and not bbls:
        raise ValueError("The Class B list is empty; refusing to clear existing flags")
    Building.objects.update(on_class_b_list=False)
    flagged = Building.objects.filter(bin__in=bins).update(on_class_b_list=True)
    flagged += Building.objects.filter(bbl__in=bbls, on_class_b_list=False).update(on_class_b_list=True)
    return flagged


# --- DOF property charges ---------------------------------------------------

def summarize_charges(rows, today):
    """Return {parid: {"owed", "unpaid_periods", "as_of"}} from Property Charges Balance rows.

    The dataset holds several extracts over time. For each parcel, billing period
    and charge code, only the row from the newest extract counts. Balances whose
    due date has not arrived are ignored.
    """
    latest = {}
    for row in rows:
        key = (row.get("parid"), row.get("dt_pd_begin"), row.get("code"))
        stamp = (str(row.get("extractdt") or ""), str(row.get("up_date") or ""))
        if key not in latest or stamp > latest[key][0]:
            latest[key] = (stamp, row)

    summary = {}
    periods = defaultdict(set)
    for (parid, period, _code), (stamp, row) in latest.items():
        entry = summary.setdefault(parid, {"owed": Decimal("0"), "unpaid_periods": 0, "as_of": None})
        extract = _date(stamp[0])
        if extract and (entry["as_of"] is None or extract > entry["as_of"]):
            entry["as_of"] = extract
        balance = _money(row.get("sum_bal"))
        due = _date(row.get("due_date"))
        if balance > 0 and (due is None or due <= today):
            entry["owed"] += balance
            periods[parid].add(period)
    for parid, entry in summary.items():
        entry["unpaid_periods"] = len(periods[parid])
    return summary


def load_tax_balances(client, today=None):
    """Set tax_owed, unpaid_periods and tax_as_of for every building with a BBL."""
    today = today or date.today()
    bbls = sorted(set(Building.objects.exclude(bbl="").values_list("bbl", flat=True)))
    select = "parid,code,dt_pd_begin,due_date,sum_bal,extractdt,up_date"
    updated = 0
    for batch in chunked(bbls, BATCH):
        rows = client.fetch_all(PROPERTY_CHARGES, where=in_clause("parid", batch), select=select)
        summary = summarize_charges(rows, today)
        for bbl in batch:
            entry = summary.get(bbl, {"owed": Decimal("0"), "unpaid_periods": 0, "as_of": None})
            updated += Building.objects.filter(bbl=bbl).update(
                tax_owed=entry["owed"], unpaid_periods=entry["unpaid_periods"], tax_as_of=entry["as_of"]
            )
    return updated


# --- Tax lien sale lists ------------------------------------------------------

def latest_lien_by_bbl(rows):
    """Return {bbl: {"stage", "month", "water_only"}} keeping each lot's most recent entry."""
    result = {}
    for row in rows:
        bbl = make_bbl(row.get("borough"), row.get("block"), row.get("lot"))
        month = _date(row.get("month"))
        if not bbl or month is None:
            continue
        if bbl not in result or month > result[bbl]["month"]:
            result[bbl] = {
                "stage": str(row.get("cycle") or ""),
                "month": month,
                "water_only": str(row.get("water_debt_only") or "").strip().upper() in ("Y", "YES", "TRUE"),
            }
    return result


def load_lien_lists(client):
    """Set lien_stage, lien_month and lien_water_only from the Tax Lien Sale Lists."""
    zips = sorted(set(Building.objects.exclude(zip_code="").values_list("zip_code", flat=True)))
    rows = []
    for batch in chunked(zips, BATCH):
        rows.extend(client.fetch_all(LIEN_LISTS, where=in_clause("zip_code", batch)))
    liens = latest_lien_by_bbl(rows)
    Building.objects.update(lien_stage="", lien_month=None, lien_water_only=False)
    updated = 0
    for bbl, entry in liens.items():
        updated += Building.objects.filter(bbl=bbl).update(
            lien_stage=entry["stage"][:40], lien_month=entry["month"], lien_water_only=entry["water_only"]
        )
    return updated


# --- HPD registrations and contacts --------------------------------------------

def _contact_name(row):
    corporation = (row.get("corporationname") or "").strip()
    person = " ".join(p for p in ((row.get("firstname") or "").strip(), (row.get("lastname") or "").strip()) if p)
    return corporation or person


def load_registrations(client):
    """Set registration_end, owner_name and agent_name from HPD registration data."""
    ids = sorted(set(Building.objects.exclude(registration_id=None).values_list("registration_id", flat=True)))
    updated = 0
    for batch in chunked(ids, BATCH):
        where = "registrationid in (" + ",".join(str(i) for i in batch) + ")"
        ends = {_int(r.get("registrationid")): _date(r.get("registrationenddate"))
                for r in client.fetch_all(HPD_REGISTRATIONS, where=where)}
        owners, agents = {}, {}
        for row in client.fetch_all(HPD_CONTACTS, where=where):
            reg_id, kind, name = _int(row.get("registrationid")), row.get("type"), _contact_name(row)
            if not name:
                continue
            if kind == "Agent":
                agents.setdefault(reg_id, name)
            elif kind in OWNER_TYPES:
                rank = OWNER_TYPES.index(kind)
                if reg_id not in owners or rank < owners[reg_id][0]:
                    owners[reg_id] = (rank, name)
        for reg_id in batch:
            updated += Building.objects.filter(registration_id=reg_id).update(
                registration_end=ends.get(reg_id),
                owner_name=owners.get(reg_id, (0, ""))[1][:200],
                agent_name=agents.get(reg_id, "")[:200],
            )
    return updated


# --- Scoring ----------------------------------------------------------------------

def score_all(today=None):
    today = today or date.today()
    count = 0
    for building in Building.objects.all().iterator():
        building.score, building.score_reasons = score_building(
            on_class_b_list=building.on_class_b_list,
            tax_owed=building.tax_owed,
            unpaid_periods=building.unpaid_periods,
            lien_stage=building.lien_stage,
            lien_water_only=building.lien_water_only,
            registration_end=building.registration_end,
            today=today,
        )
        building.save(update_fields=["score", "score_reasons"])
        count += 1
    return count
