from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from leads.services import loaders
from leads.services.classb import parse_class_b_rows, read_spreadsheet


class Command(BaseCommand):
    help = "Flag buildings that are on the city's Class B Multiple Dwellings List, then rescore."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="Path to the downloaded list (.xls, .xlsx or .csv).")

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        try:
            bins, bbls = parse_class_b_rows(read_spreadsheet(path))
            flagged = loaders.apply_class_b_list(bins, bbls)
        except ValueError as error:
            raise CommandError(str(error)) from error
        loaders.score_all()
        self.stdout.write(self.style.SUCCESS(
            f"List has {len(bins)} BINs and {len(bbls)} BBLs; {flagged} of your buildings are on it."
        ))
