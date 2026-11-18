"""Read the Office of Special Enforcement Class B Multiple Dwellings List.

The city publishes it as a spreadsheet whose column names may change, so columns
are found by name: a BIN column, a BBL column, or borough + block + lot.
Download: https://www.nyc.gov/site/specialenforcement/reporting-law/class-b-mdl.page
"""
import csv
import re
from pathlib import Path

from .bbl import make_bbl

BOROUGH_CODES = {
    "manhattan": 1, "mn": 1, "new york": 1, "bronx": 2, "bx": 2, "the bronx": 2,
    "brooklyn": 3, "bk": 3, "kings": 3, "queens": 4, "qn": 4,
    "staten island": 5, "si": 5, "richmond": 5,
}
HEADER_WORDS = {"bin", "bbl", "block", "lot", "borough", "boro"}


def _key(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _digits(value):
    """'3018734.0' or 3018734.0 -> '3018734'; anything without digits -> ''."""
    if value is None:
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text if text.isdigit() else ""


def _borough_code(value):
    digits = _digits(value)
    if digits:
        return digits
    return BOROUGH_CODES.get(str(value or "").strip().lower(), "")


def parse_class_b_rows(rows):
    """Return (set of BINs, set of BBLs) found in the spreadsheet rows (dicts keyed by header)."""
    bins, bbls = set(), set()
    for row in rows:
        cells = {_key(k): v for k, v in row.items()}
        bin_value = next((_digits(v) for k, v in cells.items() if k == "bin" or k.endswith("bin")), "")
        if len(bin_value) == 7:
            bins.add(bin_value)
        bbl_value = _digits(cells.get("bbl"))
        if len(bbl_value) == 10:
            bbls.add(bbl_value)
        elif "block" in cells and "lot" in cells:
            boro = _borough_code(cells.get("borough", cells.get("boro", cells.get("boroid"))))
            block, lot = _digits(cells.get("block")), _digits(cells.get("lot"))
            if boro and block and lot:
                bbls.add(make_bbl(boro, block, lot))
    return bins, bbls


def _rows_to_dicts(grid):
    """Find the header row (first row naming BIN/BBL/block) and key the rest by it."""
    for index, row in enumerate(grid):
        if {_key(c) for c in row if c is not None} & HEADER_WORDS:
            header = [str(c) if c is not None else f"col{i}" for i, c in enumerate(row)]
            return [dict(zip(header, data)) for data in grid[index + 1 :]]
    raise ValueError("No header row with a BIN, BBL or block column was found in the spreadsheet")


def read_spreadsheet(path):
    """Read .xlsx, .xls or .csv into a list of dicts."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with open(path, newline="", encoding="utf-8-sig") as handle:
            grid = list(csv.reader(handle))
    elif suffix == ".xls":
        import xlrd

        sheet = xlrd.open_workbook(str(path)).sheet_by_index(0)
        grid = [sheet.row_values(i) for i in range(sheet.nrows)]
    elif suffix in (".xlsx", ".xlsm"):
        import openpyxl

        sheet = openpyxl.load_workbook(str(path), read_only=True, data_only=True).worksheets[0]
        grid = [list(row) for row in sheet.iter_rows(values_only=True)]
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    return _rows_to_dicts(grid)
