from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from leads.services.scoring import score_building


def facts(**over):
    base = dict(
        on_class_b_list=False,
        tax_owed=Decimal("0"),
        unpaid_periods=0,
        lien_stage="",
        lien_water_only=False,
        registration_end=date(2030, 1, 1),
        today=date(2026, 11, 16),
    )
    base.update(over)
    return base


class ScoreBuildingTests(SimpleTestCase):
    def test_building_with_no_signals_scores_zero(self):
        score, reasons = score_building(**facts())
        self.assertEqual(score, 0)
        self.assertEqual(reasons, [])

    def test_class_b_list_adds_thirty(self):
        score, reasons = score_building(**facts(on_class_b_list=True))
        self.assertEqual(score, 30)
        self.assertIn("On city Class B list", reasons)

    def test_small_tax_debt_adds_five(self):
        score, _ = score_building(**facts(tax_owed=Decimal("1200")))
        self.assertEqual(score, 5)

    def test_tax_debt_of_five_thousand_adds_twenty(self):
        score, _ = score_building(**facts(tax_owed=Decimal("5000")))
        self.assertEqual(score, 20)

    def test_tax_debt_of_twenty_thousand_adds_thirty_five(self):
        score, reasons = score_building(**facts(tax_owed=Decimal("21000")))
        self.assertEqual(score, 35)
        self.assertIn("Owes $21,000 in property charges", reasons)

    def test_four_unpaid_periods_adds_ten(self):
        score, _ = score_building(**facts(tax_owed=Decimal("100"), unpaid_periods=4))
        self.assertEqual(score, 15)

    def test_lien_list_entry_adds_twenty_five(self):
        score, reasons = score_building(**facts(lien_stage="Final Sale"))
        self.assertEqual(score, 25)
        self.assertIn("Tax lien list: Final Sale", reasons)

    def test_water_only_lien_adds_ten(self):
        score, _ = score_building(**facts(lien_stage="90 Day Notice", lien_water_only=True))
        self.assertEqual(score, 10)

    def test_lapsed_registration_adds_five(self):
        score, reasons = score_building(**facts(registration_end=date(2025, 8, 31)))
        self.assertEqual(score, 5)
        self.assertIn("HPD registration lapsed", reasons)

    def test_missing_registration_date_is_not_counted_as_lapsed(self):
        score, _ = score_building(**facts(registration_end=None))
        self.assertEqual(score, 0)

    def test_signals_add_together(self):
        score, reasons = score_building(
            **facts(on_class_b_list=True, tax_owed=Decimal("21000"), unpaid_periods=6, lien_stage="Final Sale")
        )
        self.assertEqual(score, 100)
        self.assertEqual(len(reasons), 4)
