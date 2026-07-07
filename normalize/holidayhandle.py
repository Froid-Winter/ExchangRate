from datetime import timedelta
from .adjustdate import normalize_date

def get_last_available_date(exdate, check_func):
    exdate = normalize_date(exdate)

    # Keep going backwards until data exists
    while True:
        if check_func(exdate):
            return exdate
        exdate -= timedelta(days=1)