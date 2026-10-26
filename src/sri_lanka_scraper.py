import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from normalize.holidayhandle import get_last_available_date
from normalize.adjustdate import normalize_date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-usd-spot-exchange-rates",
    "Origin": "https://www.cbsl.gov.lk",
    "Connection": "keep-alive",
}


def _post_cbsr(base_url, session, payload, retries=3):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            r = session.post(base_url, headers=HEADERS, data=payload, timeout=30, verify=True)
            r.raise_for_status()
            return r
        except Exception as e:
            last_exc = e
            import time
            time.sleep(2 * attempt)
    raise last_exc


def scrape_sri_lanka(exdate=None):
    """
    Sri Lanka – Central Bank USD spot rate.
    Uses get_last_available_date to walk backwards until a day with data is found.
    """

    base_url = "https://www.cbsl.gov.lk/cbsl_custom/exrates/exrates_results_spot_mid.php"
    session = requests.Session()

    # 1) Decide starting date (requested or today) as 'YYYY-MM-DD'
    if exdate is None:
        start_date = datetime.utcnow().date()
        start_date_str = start_date.strftime("%Y-%m-%d")
    else:
        start_date = normalize_date(exdate)
        start_date_str = start_date.strftime("%Y-%m-%d")

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
            r = _post_cbsr(base_url, session, payload)
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

            rate_str = tds[1].get_text(strip=True).replace(",", "")
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

    try:
        r = _post_cbsr(base_url, session, payload)
    except Exception as e:
        raise RuntimeError(f"Sri Lanka request failed for {date_str}: {e}")

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
    rate_str = tds[1].get_text(strip=True).replace(",", "")

    try:
        page_date = datetime.strptime(date_page, "%Y-%m-%d").date()
        rate = float(rate_str)
    except Exception as e:
        raise RuntimeError(f"Parse failed - date='{date_page}', rate='{rate_str}': {e}")

    print(f"Sri Lanka: {rate} LKR/USD on {page_date}")

    # Use the actual page/date found for consistency with retry logic
    date_of_page_out = page_date.strftime("%Y-%m-%d") if page_date else date_str

    return [{
        "country": "Sri Lanka",
        "value": rate,
        "unit": "LKR",
        "date_of_page": date_of_page_out,
        "website": "https://www.cbsl.gov.lk/en/rates-and-indicators/exchange-rates/daily-indicative-usd-spot-exchange-rates",
        "Source": "Central Bank of Sri Lanka",
        "Status": "only one(USD->LKR)",
    }]