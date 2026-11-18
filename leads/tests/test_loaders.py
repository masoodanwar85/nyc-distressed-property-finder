from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from leads.models import Building
from leads.services import loaders
from leads.services.classb import parse_class_b_rows
from leads.services.loaders import (
    HPD_BUILDINGS, HPD_CONTACTS, HPD_REGISTRATIONS, LIEN_LISTS, PROPERTY_CHARGES,
    latest_lien_by_bbl, summarize_charges,
)
from .fakes import FakeClient, hpd_row

TODAY = date(2026, 11, 16)


def make_building(**over):
    fields = dict(hpd_building_id=1, bin="3018734", bbl="3009357504", zip_code="11217",
                  class_a_units=1, class_b_units=6, registration_id=310062, last_seen=TODAY)
    fields.update(over)
    return Building.objects.create(**fields)


class LoadHpdBuildingsTests(TestCase):
    def test_creates_building_with_units_ids_and_bbl(self):
        client = FakeClient({HPD_BUILDINGS: [hpd_row()]})
        count = loaders.load_hpd_buildings(client, ["11217"], today=TODAY)
        self.assertEqual(count, 1)
        b = Building.objects.get(hpd_building_id=132720)
        self.assertEqual((b.class_a_units, b.class_b_units), (1, 6))
        self.assertEqual(b.bin, "3018734")
        self.assertEqual(b.bbl, "3009357504")
        self.assertEqual(b.registration_id, 310062)
        self.assertEqual(b.address, "84 6 AVENUE, BROOKLYN 11217")
        self.assertEqual(b.last_seen, TODAY)

    def test_query_filters_by_zip_and_unit_rule(self):
        client = FakeClient({HPD_BUILDINGS: []})
        loaders.load_hpd_buildings(client, ["11217", "10027"], max_a=1, min_b=1, max_b=15, today=TODAY)
        where = client.calls[0]["where"]
        self.assertIn("zip in ('11217','10027')", where)
        self.assertIn("legalclassb >= 1", where)
        self.assertIn("legalclassb <= 15", where)
        self.assertIn("legalclassa <= 1", where)

    def test_second_run_updates_instead_of_duplicating(self):
        loaders.load_hpd_buildings(FakeClient({HPD_BUILDINGS: [hpd_row()]}), ["11217"], today=date(2026, 11, 9))
        loaders.load_hpd_buildings(
            FakeClient({HPD_BUILDINGS: [hpd_row(legalclassb="8")]}), ["11217"], today=TODAY
        )
        b = Building.objects.get()
        self.assertEqual(b.class_b_units, 8)
        self.assertEqual(b.first_seen, date(2026, 11, 9))
        self.assertEqual(b.last_seen, TODAY)

    def test_missing_class_a_count_is_stored_as_zero(self):
        row = hpd_row()
        del row["legalclassa"]
        loaders.load_hpd_buildings(FakeClient({HPD_BUILDINGS: [row]}), ["11217"], today=TODAY)
        self.assertEqual(Building.objects.get().class_a_units, 0)

    def test_user_status_survives_a_reload(self):
        loaders.load_hpd_buildings(FakeClient({HPD_BUILDINGS: [hpd_row()]}), ["11217"], today=TODAY)
        Building.objects.update(status=Building.Status.CONTACTED)
        loaders.load_hpd_buildings(FakeClient({HPD_BUILDINGS: [hpd_row()]}), ["11217"], today=TODAY)
        self.assertEqual(Building.objects.get().status, Building.Status.CONTACTED)


class ClassBListTests(TestCase):
    def test_parse_rows_reads_bin_column_whatever_its_case(self):
        bins, bbls = parse_class_b_rows([{"Address": "x", "BIN ": 3018734.0}, {"Address": "y", "BIN ": None}])
        self.assertEqual(bins, {"3018734"})
        self.assertEqual(bbls, set())

    def test_parse_rows_reads_bbl_column(self):
        _, bbls = parse_class_b_rows([{"bbl": "3009357504"}])
        self.assertEqual(bbls, {"3009357504"})

    def test_parse_rows_builds_bbl_from_borough_block_lot(self):
        _, bbls = parse_class_b_rows([{"Borough": "Brooklyn", "Block": 935, "Lot": 7504}])
        self.assertEqual(bbls, {"3009357504"})

    def test_apply_flags_matches_by_bin_or_bbl_and_clears_others(self):
        by_bin = make_building(hpd_building_id=1, bin="3018734", bbl="3009357504")
        by_bbl = make_building(hpd_building_id=2, bin="1030060", bbl="1011460016")
        stale = make_building(hpd_building_id=3, bin="2000001", bbl="2000010001", on_class_b_list=True)
        flagged = loaders.apply_class_b_list({"3018734"}, {"1011460016"})
        self.assertEqual(flagged, 2)
        for b in (by_bin, by_bbl, stale):
            b.refresh_from_db()
        self.assertTrue(by_bin.on_class_b_list)
        self.assertTrue(by_bbl.on_class_b_list)
        self.assertFalse(stale.on_class_b_list)

    def test_apply_refuses_an_empty_list(self):
        make_building(on_class_b_list=True)
        with self.assertRaises(ValueError):
            loaders.apply_class_b_list(set(), set())
        self.assertTrue(Building.objects.get().on_class_b_list)


def charge(**over):
    row = {"parid": "3009357504", "code": "CHG", "dt_pd_begin": "2025-07-01T00:00:00.000",
           "due_date": "2025-07-01T00:00:00.000", "sum_bal": "1000.50",
           "extractdt": "2026-11-01T00:00:00.000", "up_date": "2026-10-01T00:00:00.000"}
    row.update(over)
    return row


class SummarizeChargesTests(SimpleTestCase):
    def test_sums_open_balances_per_parcel(self):
        rows = [charge(), charge(dt_pd_begin="2025-10-01T00:00:00.000", due_date="2025-10-01T00:00:00.000", sum_bal="500")]
        summary = summarize_charges(rows, TODAY)
        self.assertEqual(summary["3009357504"]["owed"], Decimal("1500.50"))
        self.assertEqual(summary["3009357504"]["unpaid_periods"], 2)
        self.assertEqual(summary["3009357504"]["as_of"], date(2026, 11, 1))

    def test_newer_extract_replaces_older_row_for_same_period(self):
        rows = [charge(extractdt="2025-09-01T00:00:00.000", sum_bal="1000"),
                charge(extractdt="2026-11-01T00:00:00.000", sum_bal="0")]
        summary = summarize_charges(rows, TODAY)
        self.assertEqual(summary["3009357504"]["owed"], Decimal("0"))
        self.assertEqual(summary["3009357504"]["unpaid_periods"], 0)

    def test_charges_not_yet_due_are_ignored(self):
        rows = [charge(dt_pd_begin="2027-01-01T00:00:00.000", due_date="2027-01-01T00:00:00.000")]
        self.assertEqual(summarize_charges(rows, TODAY)["3009357504"]["owed"], Decimal("0"))

    def test_two_charge_codes_in_one_period_count_as_one_period(self):
        rows = [charge(), charge(code="INT", sum_bal="20")]
        summary = summarize_charges(rows, TODAY)
        self.assertEqual(summary["3009357504"]["owed"], Decimal("1020.50"))
        self.assertEqual(summary["3009357504"]["unpaid_periods"], 1)


class LoadTaxBalancesTests(TestCase):
    def test_writes_owed_and_periods_and_zeroes_parcels_with_no_rows(self):
        owing = make_building(hpd_building_id=1, bbl="3009357504")
        clear = make_building(hpd_building_id=2, bbl="1011460016", tax_owed=Decimal("99"), unpaid_periods=3)
        client = FakeClient({PROPERTY_CHARGES: [charge()]})
        loaders.load_tax_balances(client, today=TODAY)
        owing.refresh_from_db(); clear.refresh_from_db()
        self.assertEqual(owing.tax_owed, Decimal("1000.50"))
        self.assertEqual(owing.unpaid_periods, 1)
        self.assertEqual(owing.tax_as_of, date(2026, 11, 1))
        self.assertEqual(clear.tax_owed, Decimal("0"))
        self.assertEqual(clear.unpaid_periods, 0)
        self.assertIn("parid in ('", client.calls[0]["where"])


def lien(**over):
    row = {"month": "2025-06-01T00:00:00.000", "cycle": "Final Sale", "borough": "3", "block": "935",
           "lot": "7504", "zip_code": "11217", "water_debt_only": "N"}
    row.update(over)
    return row


class LienTests(TestCase):
    def test_latest_month_wins(self):
        result = latest_lien_by_bbl([lien(month="2019-05-01T00:00:00.000", cycle="Final Sale"),
                                     lien(month="2025-03-01T00:00:00.000", cycle="90 Day Notice")])
        self.assertEqual(result["3009357504"]["stage"], "90 Day Notice")
        self.assertEqual(result["3009357504"]["month"], date(2025, 3, 1))

    def test_water_debt_flag_is_read(self):
        result = latest_lien_by_bbl([lien(water_debt_only="Y")])
        self.assertTrue(result["3009357504"]["water_only"])

    def test_load_sets_lien_fields_and_clears_buildings_not_listed(self):
        listed = make_building(hpd_building_id=1, bbl="3009357504", zip_code="11217")
        gone = make_building(hpd_building_id=2, bbl="1011460016", zip_code="10023", lien_stage="Final Sale")
        client = FakeClient({LIEN_LISTS: [lien()]})
        loaders.load_lien_lists(client)
        listed.refresh_from_db(); gone.refresh_from_db()
        self.assertEqual(listed.lien_stage, "Final Sale")
        self.assertEqual(listed.lien_month, date(2025, 6, 1))
        self.assertEqual(gone.lien_stage, "")
        self.assertIsNone(gone.lien_month)
        self.assertIn("zip_code in (", client.calls[0]["where"])


class LoadRegistrationsTests(TestCase):
    def test_sets_registration_end_owner_and_agent(self):
        b = make_building(registration_id=310062)
        client = FakeClient({
            HPD_REGISTRATIONS: [{"registrationid": "310062", "registrationenddate": "2025-08-31T00:00:00.000"}],
            HPD_CONTACTS: [
                {"registrationid": "310062", "type": "CorporateOwner", "corporationname": "84 SIXTH LLC"},
                {"registrationid": "310062", "type": "Agent", "firstname": "JANE", "lastname": "DOE"},
                {"registrationid": "310062", "type": "SiteManager", "firstname": "IGNORED", "lastname": "PERSON"},
            ],
        })
        loaders.load_registrations(client)
        b.refresh_from_db()
        self.assertEqual(b.registration_end, date(2025, 8, 31))
        self.assertEqual(b.owner_name, "84 SIXTH LLC")
        self.assertEqual(b.agent_name, "JANE DOE")

    def test_individual_owner_used_when_no_corporate_owner(self):
        b = make_building(registration_id=5)
        client = FakeClient({
            HPD_REGISTRATIONS: [],
            HPD_CONTACTS: [{"registrationid": "5", "type": "IndividualOwner", "firstname": "SAM", "lastname": "LEE"}],
        })
        loaders.load_registrations(client)
        b.refresh_from_db()
        self.assertEqual(b.owner_name, "SAM LEE")


class ScoreAllTests(TestCase):
    def test_score_and_reasons_are_saved(self):
        b = make_building(on_class_b_list=True, tax_owed=Decimal("21000"))
        loaders.score_all(today=TODAY)
        b.refresh_from_db()
        self.assertEqual(b.score, 65)
        self.assertEqual(b.score_reasons, ["On city Class B list", "Owes $21,000 in property charges"])

    def test_verification_level_follows_class_b_list(self):
        self.assertEqual(make_building(hpd_building_id=1, on_class_b_list=True).verification_level, "listed")
        self.assertEqual(make_building(hpd_building_id=2).verification_level, "unverified")
