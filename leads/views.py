import csv
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from .models import Building, Note, Run


def filtered_buildings(params):
    """Apply the list filters shared by the lead list and the CSV export."""
    buildings = Building.objects.all()
    if params.get("zip"):
        buildings = buildings.filter(zip_code=params["zip"])
    if params.get("class_b") == "1":
        buildings = buildings.filter(on_class_b_list=True)
    if params.get("status"):
        buildings = buildings.filter(status=params["status"])
    if params.get("min_owed"):
        try:
            buildings = buildings.filter(tax_owed__gte=Decimal(params["min_owed"]))
        except InvalidOperation:
            pass
    return buildings.order_by("-score", "-tax_owed", "hpd_building_id")


@login_required
def lead_list(request):
    page = Paginator(filtered_buildings(request.GET), 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "page": page,
        "total": page.paginator.count,
        "zip_codes": Building.objects.exclude(zip_code="").values_list("zip_code", flat=True).distinct().order_by("zip_code"),
        "statuses": Building.Status.choices,
        "filters": request.GET,
        "querystring": query.urlencode(),
        "last_run": Run.objects.first(),
    }
    return render(request, "leads/lead_list.html", context)


@login_required
def lead_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="nyc-leads.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Score", "Address", "BIN", "BBL", "Class A units", "Class B units", "On city Class B list",
        "Tax owed", "Unpaid periods", "Lien stage", "Lien month", "Owner", "Agent", "Status",
        "Why", "DOB certificates", "HPD Online",
    ])
    for b in filtered_buildings(request.GET):
        writer.writerow([
            b.score, b.address, b.bin, b.bbl, b.class_a_units, b.class_b_units,
            "Yes" if b.on_class_b_list else "No", b.tax_owed, b.unpaid_periods, b.lien_stage,
            b.lien_month or "", b.owner_name, b.agent_name, b.get_status_display(),
            "; ".join(b.score_reasons), b.dob_certificates_url, b.hpd_online_url,
        ])
    return response


@login_required
def lead_detail(request, pk):
    building = get_object_or_404(Building, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "note":
            text = request.POST.get("text", "").strip()
            if text:
                Note.objects.create(building=building, author=request.user, text=text)
        elif action == "status":
            status = request.POST.get("status")
            if status not in Building.Status.values:
                return HttpResponseBadRequest("Unknown status")
            building.status = status
            building.save(update_fields=["status"])
        else:
            return HttpResponseBadRequest("Unknown action")
        return redirect("lead_detail", pk=building.pk)
    return render(request, "leads/lead_detail.html", {"b": building, "statuses": Building.Status.choices})


@login_required
def run_list(request):
    return render(request, "leads/run_list.html", {"runs": Run.objects.all()[:50]})
