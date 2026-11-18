"""Transparent lead score: each signal adds points and a plain-language reason.

Change the weights here after the client reviews the first lists.
"""
from decimal import Decimal

CLASS_B_LIST_POINTS = 30
TAX_SMALL_POINTS = 5
TAX_MEDIUM_POINTS = 20
TAX_LARGE_POINTS = 35
TAX_MEDIUM_THRESHOLD = Decimal("5000")
TAX_LARGE_THRESHOLD = Decimal("20000")
MANY_UNPAID_PERIODS = 4
MANY_UNPAID_PERIODS_POINTS = 10
LIEN_POINTS = 25
LIEN_WATER_ONLY_POINTS = 10
LAPSED_REGISTRATION_POINTS = 5


def score_building(*, on_class_b_list, tax_owed, unpaid_periods, lien_stage, lien_water_only, registration_end, today):
    """Return (score, reasons) for one building."""
    score = 0
    reasons = []

    if on_class_b_list:
        score += CLASS_B_LIST_POINTS
        reasons.append("On city Class B list")

    if tax_owed > 0:
        if tax_owed >= TAX_LARGE_THRESHOLD:
            score += TAX_LARGE_POINTS
        elif tax_owed >= TAX_MEDIUM_THRESHOLD:
            score += TAX_MEDIUM_POINTS
        else:
            score += TAX_SMALL_POINTS
        reasons.append(f"Owes ${tax_owed:,.0f} in property charges")

    if unpaid_periods >= MANY_UNPAID_PERIODS:
        score += MANY_UNPAID_PERIODS_POINTS
        reasons.append(f"{unpaid_periods} unpaid billing periods")

    if lien_stage:
        score += LIEN_WATER_ONLY_POINTS if lien_water_only else LIEN_POINTS
        suffix = " (water debt only)" if lien_water_only else ""
        reasons.append(f"Tax lien list: {lien_stage}{suffix}")

    if registration_end is not None and registration_end < today:
        score += LAPSED_REGISTRATION_POINTS
        reasons.append("HPD registration lapsed")

    return score, reasons
