"""The weekly run: load every source, score, and record what happened."""
from datetime import date

from django.utils import timezone

from leads.models import Building, Run
from . import loaders
from .classb import parse_class_b_rows, read_spreadsheet


def run_pipeline(client, zip_codes, class_b_file=None, today=None, log=lambda message: None):
    if not zip_codes:
        raise ValueError("No zip codes given. Set TARGET_ZIP_CODES in .env or pass --zips.")
    today = today or date.today()
    run = Run.objects.create()
    summary = {"zip_codes": list(zip_codes)}
    try:
        log("Loading HPD buildings...")
        summary["buildings"] = loaders.load_hpd_buildings(client, zip_codes, today=today)
        if class_b_file:
            log("Applying Class B list...")
            bins, bbls = parse_class_b_rows(read_spreadsheet(class_b_file))
            summary["class_b_list"] = loaders.apply_class_b_list(bins, bbls)
        else:
            summary["class_b_list"] = "skipped (no file given)"
        log("Loading tax balances...")
        summary["tax_rows"] = loaders.load_tax_balances(client, today=today)
        log("Loading lien lists...")
        summary["lien_matches"] = loaders.load_lien_lists(client)
        log("Loading registrations...")
        summary["registrations"] = loaders.load_registrations(client)
        log("Scoring...")
        summary["scored"] = loaders.score_all(today=today)
        summary["total_candidates"] = Building.objects.count()
        summary["new_this_run"] = Building.objects.filter(first_seen=today).count()
        run.ok = True
    except Exception as error:
        run.error = f"{type(error).__name__}: {error}"
        raise
    finally:
        run.summary = summary
        run.finished = timezone.now()
        run.save()
    return run
