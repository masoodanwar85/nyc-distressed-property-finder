import csv
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from leads.models import Building, Note


def make_building(n, **over):
    fields = dict(hpd_building_id=n, bin=f"30000{n:02d}", bbl=f"30000100{n:02d}", house_number=str(n),
                  street_name="TEST STREET", borough="BROOKLYN", zip_code="11217",
                  class_a_units=0, class_b_units=5, last_seen=date(2026, 11, 16))
    fields.update(over)
    return Building.objects.create(**fields)


class ViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("client", password="pw-for-tests")
        self.client.force_login(self.user)

    def test_lead_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("lead_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_lead_list_orders_by_score_highest_first(self):
        make_building(1, score=10)
        make_building(2, score=90)
        response = self.client.get(reverse("lead_list"))
        ids = [b.hpd_building_id for b in response.context["page"].object_list]
        self.assertEqual(ids, [2, 1])

    def test_filter_by_minimum_tax_owed(self):
        make_building(1, tax_owed=Decimal("500"))
        make_building(2, tax_owed=Decimal("21000"))
        response = self.client.get(reverse("lead_list"), {"min_owed": "5000"})
        self.assertEqual([b.hpd_building_id for b in response.context["page"].object_list], [2])

    def test_filter_by_class_b_list_zip_and_status(self):
        make_building(1, on_class_b_list=True, zip_code="11217")
        make_building(2, on_class_b_list=False, zip_code="11217")
        make_building(3, on_class_b_list=True, zip_code="10027", status=Building.Status.REJECTED)
        get = lambda **q: [b.hpd_building_id for b in self.client.get(reverse("lead_list"), q).context["page"].object_list]
        self.assertEqual(sorted(get(class_b="1")), [1, 3])
        self.assertEqual(get(class_b="1", zip="11217"), [1])
        self.assertEqual(get(status="rejected"), [3])

    def test_invalid_minimum_is_ignored(self):
        make_building(1)
        response = self.client.get(reverse("lead_list"), {"min_owed": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"].object_list), 1)

    def test_csv_export_has_header_and_filtered_rows(self):
        make_building(1, tax_owed=Decimal("21000"), owner_name="84 SIXTH LLC", score=35,
                      score_reasons=["Owes $21,000 in property charges"])
        make_building(2, tax_owed=Decimal("0"))
        response = self.client.get(reverse("lead_export"), {"min_owed": "1"})
        self.assertEqual(response["Content-Type"], "text/csv")
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0][:4], ["Score", "Address", "BIN", "BBL"])
        self.assertEqual(len(rows), 2)
        self.assertIn("84 SIXTH LLC", rows[1])
        self.assertIn("21000.00", rows[1])

    def test_detail_page_shows_building_and_city_record_links(self):
        b = make_building(1)
        response = self.client.get(reverse("lead_detail", args=[b.pk]))
        self.assertContains(response, "1 TEST STREET")
        self.assertContains(response, "allbin=3000001")
        self.assertContains(response, "/building/1/historical")

    def test_posting_a_note_saves_it_with_the_author(self):
        b = make_building(1)
        self.client.post(reverse("lead_detail", args=[b.pk]), {"action": "note", "text": "Called the agent"})
        note = Note.objects.get()
        self.assertEqual((note.building, note.author, note.text), (b, self.user, "Called the agent"))

    def test_blank_note_is_not_saved(self):
        b = make_building(1)
        self.client.post(reverse("lead_detail", args=[b.pk]), {"action": "note", "text": "   "})
        self.assertEqual(Note.objects.count(), 0)

    def test_posting_a_status_updates_the_building(self):
        b = make_building(1)
        self.client.post(reverse("lead_detail", args=[b.pk]), {"action": "status", "status": "contacted"})
        b.refresh_from_db()
        self.assertEqual(b.status, "contacted")

    def test_unknown_status_is_rejected(self):
        b = make_building(1)
        response = self.client.post(reverse("lead_detail", args=[b.pk]), {"action": "status", "status": "bogus"})
        self.assertEqual(response.status_code, 400)
        b.refresh_from_db()
        self.assertEqual(b.status, "new")

    def test_run_history_page_loads(self):
        self.assertEqual(self.client.get(reverse("run_list")).status_code, 200)
