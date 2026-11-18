from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from leads.services.pipeline import run_pipeline
from leads.services.socrata import make_client


class Command(BaseCommand):
    help = "Load all data sources for the target zip codes, score the buildings and record the run."

    def add_arguments(self, parser):
        parser.add_argument("--zips", help="Comma-separated zip codes. Defaults to TARGET_ZIP_CODES in .env.")
        parser.add_argument("--class-b-file", help="Path to the OSE Class B list (.xls, .xlsx or .csv).")

    def handle(self, *args, **options):
        zips = [z.strip() for z in (options["zips"] or "").split(",") if z.strip()] or settings.TARGET_ZIP_CODES
        if not zips:
            raise CommandError("No zip codes. Pass --zips 10027,10030 or set TARGET_ZIP_CODES in .env.")
        class_b_file = options["class_b_file"] or getattr(settings, "CLASS_B_LIST_FILE", "") or None
        try:
            run = run_pipeline(make_client(), zips, class_b_file=class_b_file, log=self.stdout.write)
        except Exception as error:
            raise CommandError(f"Pipeline failed: {error}") from error
        total = run.summary["total_candidates"]
        self.stdout.write(self.style.SUCCESS(
            f"Done: {total} candidate{'s' if total != 1 else ''} "
            f"({run.summary['new_this_run']} new), Class B list: {run.summary['class_b_list']}."
        ))
