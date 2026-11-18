import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from leads.models import Building, Run
from .test_loaders import make_building
from .test_pipeline import full_client


class RunPipelineCommandTests(TestCase):
    def test_zips_argument_runs_the_pipeline_and_prints_a_summary(self):
        out = io.StringIO()
        with mock.patch("leads.management.commands.run_pipeline.make_client", return_value=full_client()):
            call_command("run_pipeline", "--zips", "11217", stdout=out)
        self.assertEqual(Building.objects.count(), 1)
        self.assertTrue(Run.objects.get().ok)
        self.assertIn("1 candidate", out.getvalue())

    @override_settings(TARGET_ZIP_CODES=[])
    def test_missing_zip_codes_gives_a_clear_error(self):
        with mock.patch("leads.management.commands.run_pipeline.make_client", return_value=full_client()):
            with self.assertRaises(CommandError) as raised:
                call_command("run_pipeline")
        self.assertIn("TARGET_ZIP_CODES", str(raised.exception))

    @override_settings(TARGET_ZIP_CODES=["11217"])
    def test_zip_codes_default_to_settings(self):
        with mock.patch("leads.management.commands.run_pipeline.make_client", return_value=full_client()):
            call_command("run_pipeline", stdout=io.StringIO())
        self.assertEqual(Run.objects.get().summary["zip_codes"], ["11217"])


class LoadClassBListCommandTests(TestCase):
    def test_flags_buildings_from_file_and_rescores(self):
        b = make_building()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "classb.csv"
            path.write_text("BIN\n3018734\n")
            call_command("load_class_b_list", "--file", str(path), stdout=io.StringIO())
        b.refresh_from_db()
        self.assertTrue(b.on_class_b_list)
        self.assertEqual(b.score, 30)

    def test_missing_file_gives_a_clear_error(self):
        with self.assertRaises(CommandError):
            call_command("load_class_b_list", "--file", "/no/such/file.xlsx")
