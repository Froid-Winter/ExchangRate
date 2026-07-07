import requests
from datetime import datetime, date
from normalize.adjustdate import normalize_date
from normalize.holidayhandle import get_last_available_date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

def scrape_myanmar(exdate=None):
    base_url = "https://forex.cbm.gov.mm/api/history"

    # If no date provided, start from "today" (UTC) as YYYY-MM-DD string
    if exdate is None:
        start_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        start_date_str = exdate  # expected "YYYY-MM-DD"

    def myanmar_has_data(check_date: date) -> bool:
        """
        Returns True if CBM API has USD data for the given date.
        API format is dd-mm-yyyy.
        """
        dt_for_api = check_date.strftime("%d-%m-%Y")
        url = f"{base_url}/{dt_for_api}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                return False

            data = r.json()

            # According to your comment, "no data" => [] (empty list)
            if isinstance(data, list):
                return False

            # Should be a dict with "rates" and "USD"
            rates = data.get("rates", {})
            return "USD" in rates
        except Exception:
            return False

    # 1) Find the last date that actually has data
    real_date = get_last_available_date(start_date_str, myanmar_has_data)
    dt_for_api = real_date.strftime("%d-%m-%Y")
    dt_for_page = real_date.strftime("%Y-%m-%d")

    # 2) Fetch the actual data for that date
    url = f"{base_url}/{dt_for_api}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()

    data = r.json()

    # Handle unexpected formats defensively
    if isinstance(data, list):
        if not data:
            raise ValueError(f"No Myanmar CBM rate data for date {dt_for_page}")
        else:
            raise ValueError(f"Unexpected JSON format from CBM API for date {dt_for_page}: list with elements")

    rates = data.get("rates", {})
    if "USD" not in rates:
        raise ValueError(f"USD rate not found in CBM response for date {dt_for_page}")

    usd_rate_str = rates["USD"]
    usd_rate = float(usd_rate_str)

    return [{
        "country": "Myanmar",
        "value": usd_rate,                        # e.g. 2100.0
        "unit": "MMK",                            # 1 USD = X MMK
        "requested_date": exdate or start_date_str,  # what you asked for
        "date_of_page": exdate.strftime("%Y-%m-%d"),              # actual data date (after holiday adjustment)
        "website": "https://forex.cbm.gov.mm/index.php/fxrate/history",
        "Source": "Central Bank of Myanmar",
        "Status": "only one"
    }]