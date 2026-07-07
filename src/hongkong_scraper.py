import requests
from datetime import date
from normalize.holidayhandle import get_last_available_date
from normalize.adjustdate import adjust_hongkong

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

def scrape_hongkong(exdate: str):
    def hongkong_has_data(check_date: date):
        """Return True if HKAB has data for the given date."""
        # check_date is a date object here
        date_str = check_date.strftime("%Y-%m-%d")
        target = adjust_hongkong(date_str)  # whatever format HK API needs
        url = f"https://www.hkab.org.hk/api/member/public/getExrate/{target}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                return False

            data = r.json()
            if not data:
                return False

            # Must contain valid fields
            return ("USDSelling" in data) and ("USDBuyingTT" in data)
        except Exception:
            return False

    # Step 1 — find the actual available date (returns a date object)
    real_date = get_last_available_date(exdate, hongkong_has_data)

    # Step 2 — format for API using the REAL date
    real_date_str = real_date.strftime("%Y-%m-%d")
    target = adjust_hongkong(real_date_str)
    HIST_URL = f"https://www.hkab.org.hk/api/member/public/getExrate/{target}"

    # Step 3 — fetch actual data
    r = requests.get(HIST_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()

    sell = float(data["USDSelling"])
    buy  = float(data["USDBuyingTT"])
    mid  = (sell + buy) / 2.0

    # Step 4 — return full record
    return [{
        "country": "Hong Kong",
        "value": mid,
        "unit": "HKD",
        "website": "https://www.hkab.org.hk/en/rates/exchange-rates",
        # use *actual* last available date, not the requested one
        "date_of_page": exdate.strftime("%Y-%m-%d"),
        "Source": "The Hong Kong Association of Banks",
        "Status": "buy, sell",
    }]