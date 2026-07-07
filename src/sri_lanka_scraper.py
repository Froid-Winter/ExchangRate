import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from normalize.holidayhandle import get_last_available_date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

def scrape_sri_lanka(exdate=None):
    """
    Sri Lanka – Central Bank USD spot rate.
    Uses get_last_available_date to walk backwards until a day with data is found.
    """

    base_url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results_spot_mid.php"

    # 1) Decide starting date (requested or today) as 'YYYY-MM-DD'
    if exdate is None:
        start_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        start_date_str = str(exdate).strip()  # expected 'YYYY-MM-DD'

    # 2) Define "has data" checker for a given date
    def sri_lanka_has_data(check_date: date) -> bool:
        date_str = check_date.strftime("%Y-%m-%d")
        payload = {
            "txtStart": date_str,
            "txtEnd": date_str,
            "chk_cur[]": "USD~US Dollar",
            "rangeType": "dates",
            "submit_button": "Submit",
            "lookupPage": "lookup_daily_exchange_rates.php",
            "startRange": "2006-11-11",
        }
        try:
            r = requests.post(base_url, headers=HEADERS, data=payload, timeout=15)
            if r.status_code != 200:
                return False

            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table is None:
                return False

            rows = table.find_all("tr")
            if len(rows) < 2:
                return False

            tds = rows[1].find_all("td")
            if len(tds) < 2:
                return False

            rate_str = tds[1].get_text(strip=True)
            float(rate_str)  # just to confirm it's numeric
            return True
        except Exception:
            return False

    # 3) Find last date that actually has data
    real_date = get_last_available_date(start_date_str, sri_lanka_has_data)
    date_str = real_date.strftime("%Y-%m-%d")

    # 4) Fetch actual data for that date
    payload = {
        "txtStart": date_str,
        "txtEnd": date_str,
        "chk_cur[]": "USD~US Dollar",
        "rangeType": "dates",
        "submit_button": "Submit",
        "lookupPage": "lookup_daily_exchange_rates.php",
        "startRange": "2006-11-11",
    }

    r = requests.post(base_url, headers=HEADERS, data=payload, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("No <table> in results - check date validity.")

    rows = table.find_all("tr")
    if len(rows) < 2:
        raise RuntimeError("Table has no data rows.")

    tds = rows[1].find_all("td")
    if len(tds) < 2:
        raise RuntimeError(f"Too few columns: {[t.get_text(strip=True) for t in tds]}")

    date_page = tds[0].get_text(strip=True)
    rate_str = tds[1].get_text(strip=True)

    try:
        page_date = datetime.strptime(date_page, "%Y-%m-%d").date()
        rate = float(rate_str)
    except Exception as e:
        raise RuntimeError(f"Parse failed - date='{date_page}', rate='{rate_str}': {e}")

    print(f"Sri Lanka: {rate} LKR/USD on {page_date}")

    return [{
        "country": "Sri Lanka",
        "value": rate,
        "unit": "LKR",
        "date_of_page": exdate.strftime("%Y-%m-%d"),
        "website": "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-usd-spot-exchange-rates",
        "Source": "Central Bank of Sri Lanka",
        "Status": "only one(USD->LKR)",
    }]