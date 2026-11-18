from django.conf import settings
from django.db import models


class Building(models.Model):
    """One candidate building from HPD's records, with its distress signals."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Reviewing"
        CONTACTED = "contacted", "Contacted"
        NEGOTIATING = "negotiating", "In negotiation"
        REJECTED = "rejected", "Rejected"

    # Identity (HPD "Buildings Subject to HPD Jurisdiction", kj4p-ruqc)
    hpd_building_id = models.IntegerField(unique=True)
    bin = models.CharField("BIN", max_length=7, blank=True, db_index=True)
    bbl = models.CharField("BBL", max_length=10, blank=True, db_index=True)
    registration_id = models.IntegerField(null=True, blank=True, db_index=True)
    house_number = models.CharField(max_length=20, blank=True)
    street_name = models.CharField(max_length=100, blank=True)
    borough = models.CharField(max_length=20, blank=True)
    zip_code = models.CharField(max_length=5, blank=True, db_index=True)
    class_a_units = models.IntegerField(default=0)
    class_b_units = models.IntegerField(default=0)
    dob_building_class = models.CharField(max_length=100, blank=True)

    # City-confirmed Class B (OSE list)
    on_class_b_list = models.BooleanField(default=False)

    # Tax (DOF Property Charges Balance, scjx-j6np)
    tax_owed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    unpaid_periods = models.IntegerField(default=0)
    tax_as_of = models.DateField(null=True, blank=True)

    # Lien sale lists (9rz4-mjek)
    lien_stage = models.CharField(max_length=40, blank=True)
    lien_month = models.DateField(null=True, blank=True)
    lien_water_only = models.BooleanField(default=False)

    # Owner (HPD registrations tesw-yqqr, contacts feu5-w2e2)
    owner_name = models.CharField(max_length=200, blank=True)
    agent_name = models.CharField(max_length=200, blank=True)
    registration_end = models.DateField(null=True, blank=True)

    # Ranking and workflow
    score = models.IntegerField(default=0, db_index=True)
    score_reasons = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    first_seen = models.DateField(null=True, blank=True)
    last_seen = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-score", "-tax_owed"]

    def __str__(self):
        return self.address

    @property
    def address(self):
        street = f"{self.house_number} {self.street_name}".strip()
        return f"{street}, {self.borough} {self.zip_code}".strip()

    @property
    def verification_level(self):
        """`listed` = on the city's Class B list; `unverified` = HPD unit counts only."""
        return "listed" if self.on_class_b_list else "unverified"

    @property
    def dob_certificates_url(self):
        if not self.bin:
            return ""
        return f"https://a810-bisweb.nyc.gov/bisweb/COsByLocationServlet?requestid=0&allbin={self.bin}"

    @property
    def hpd_online_url(self):
        return f"https://hpdonline.nyc.gov/hpdonline/building/{self.hpd_building_id}/historical"


class Note(models.Model):
    building = models.ForeignKey(Building, related_name="notes", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    text = models.TextField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]


class Run(models.Model):
    """One execution of the weekly pipeline."""

    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-started"]
