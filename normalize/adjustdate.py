import re
from datetime import datetime, date
import pandas as pd
from calendar import monthrange

def normalize_date(exdate):
    if exdate is None:
        return date.today()

    if isinstance(exdate, date):
        return exdate

    if isinstance(exdate, str):
        return datetime.strptime(exdate, "%Y-%m-%d").date()

    if isinstance(exdate, datetime):
        return exdate.date()

    raise ValueError(f"Unsupported type: {type(exdate)}")

def last_day_of_month(d: date) -> date:
    _, last_day = monthrange(d.year, d.month)
    return d.replace(day=last_day)

def is_missing(v):
    """Check if value is missing/empty/NA"""
    if v is None:
        return True
    if pd.isna(v):
        return True
    s = str(v).strip()
    return s == "" or s.upper() in ["NA", "N/A", "NAN", "...", "-", "—"]

def adjust_date_egypt(exdate):
    dt = normalize_date(exdate)
    return dt.strftime("%b/%m/%y")

def adjust_hongkong(exdate):
    dt = normalize_date(exdate)
    return dt.strftime("%Y-%m-%d")

def adjust_date_indonesia(exdate):
    # Parse input (assuming YYYY-MM-DD)
    dt = normalize_date(exdate)
    # Return in DD-Mon-YYYY format, e.g., 03-Feb-2026
    return dt.strftime("%d-%b-%Y")

def _is_number_line(s: str) -> bool:
    s = s.strip()
    if not s:
        return False
    # digits, optional commas, optional decimal part – e.g. 280.95, 1,234.50
    return bool(re.fullmatch(r"\d[\d,]*\.?\d*", s))