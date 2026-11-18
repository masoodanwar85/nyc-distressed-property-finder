"""Borough-block-lot (BBL) helpers. A BBL is 1 digit borough + 5 digit block + 4 digit lot."""


def make_bbl(boro, block, lot):
    """Build the 10-character BBL, or "" when any part is missing."""
    parts = [str(p).strip() if p is not None else "" for p in (boro, block, lot)]
    if not all(parts):
        return ""
    boro, block, lot = parts
    return f"{int(boro)}{int(block):05d}{int(lot):04d}"


def split_bbl(bbl):
    """Return (borough, block, lot) as integers."""
    return int(bbl[0]), int(bbl[1:6]), int(bbl[6:10])
