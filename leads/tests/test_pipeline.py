import csv
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.test import SimpleTestCase, TestCase

from leads.models import Building, Run
from leads.services.classb import read_spreadsheet
from leads.services.loaders import HPD_BUILDINGS, HPD_CONTACTS, HPD_REGISTRATIONS, LIEN_LISTS, PROPERTY_CHARGES
from leads.services.pipeline import run_pipeline
from .fakes import FakeClient, hpd_row

TODAY = date(2026, 11, 16)


class ReadSpreadsheetTests(SimpleTestCase):
    def test_reads_csv_with_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "classb.csv"
            with open(path, "w", newline="") as handle:
                csv.writer(handle).writerows([["Address", "BIN"], ["84 6 AVENUE", "3018734"]])
            self.assertEqual(read_spreadsheet(path), [{"Address": "84 6 AVENUE", "BIN": "3018734"}])

    def test_reads_xlsx_and_skips_title_rows_above_the_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "classb.xlsx"
            book = openpyxl.Workbook()
            sheet = book.active
            sheet.append(["Class B Multiple Dwellings List", None])
            sheet.append(["Address", "BIN"])
            sheet.append(["84 6 AVENUE", 3018734])
            book.save(path)
            self.assertEqual(read_spreadsheet(path), [{"Address": "84 6 AVENUE", "BIN": 3018734}])

    def test_file_without_identifier_columns_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrong.csv"
            path.write_text("Name,Phone\nA,1\n")
            with self.assertRaises(ValueError):
                read_spreadsheet(path)


def full_client():
    return FakeClient({
        HPD_BUILDINGS: [hpd_row()],
        PROPERTY_CHARGES: [{"parid": "3009357504", "code": "CHG", "dt_pd_begin": "2025-07-01T00:00:00.000",
                            "due_date": "2025-07-01T00:00:00.000", "sum_bal": "21000",
                            "extractdt": "2026-11-01T00:00:00.000"}],
        LIEN_LISTS: [{"month": "2025-06-01T00:00:00.000", "cycle": "Final Sale", "borough": "3",
                      "block": "935", "lot": "7504", "zip_code": "11217", "water_debt_only": "N"}],
        HPD_REGISTRATIONS: [{"registrationid": "310062", "registrationenddate": "2027-08-31T00:00:00.000"}],
        HPD_CONTACTS: [{"registrationid": "310062", "type": "CorporateOwner", "corporationname": "84 SIXTH LLC"}],
    })


class RunPipelineTests(TestCase):
    def test_full_run_loads_scores_and_records_the_run(self):
        run = run_pipeline(full_client(), ["11217"], today=TODAY)
        b = Building.objects.get()
        self.assertEqual(b.tax_owed, Decimal("21000"))
        self.assertEqual(b.lien_stage, "Final Sale")
        self.assertEqual(b.owner_name, "84 SIXTH LLC")
        self.assertEqual(b.score, 60)
        self.assertTrue(run.ok)
        self.assertIsNotNone(run.finished)
        self.assertEqual(run.summary["buildings"], 1)
        self.assertEqual(run.summary["class_b_list"], "skipped (no file given)")

    def test_class_b_file_is_applied_when_given(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "classb.csv"
            path.write_text("BIN\n3018734\n")
            run = run_pipeline(full_client(), ["11217"], class_b_file=path, today=TODAY)
        self.assertTrue(Building.objects.get().on_class_b_list)
        self.assertEqual(run.summary["class_b_list"], 1)
        self.assertEqual(Building.objects.get().score, 90)

    def test_failure_is_recorded_and_raised(self):
        class Broken:
            def fetch_all(self, *args, **kwargs):
                raise RuntimeError("HTTP 503")

        with self.assertRaises(RuntimeError):
            run_pipeline(Broken(), ["11217"], today=TODAY)
        run = Run.objects.get()
        self.assertFalse(run.ok)
        self.assertIn("HTTP 503", run.error)

    def test_no_zip_codes_is_an_error(self):
        with self.assertRaises(ValueError):
            run_pipeline(full_client(), [], today=TODAY)
