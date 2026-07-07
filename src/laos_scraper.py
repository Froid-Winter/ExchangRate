import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import re
from normalize.holidayhandle import get_last_available_date


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

def scrape_lao(exdate: str):
    url = "https://www.bol.gov.la/en/ExchangRate"

    def lao_has_data(check_date: date) -> bool:
        """Return True if BOL has USD data for this date."""
        query_date_str = check_date.strftime("%d-%m-%Y")

        payload = {
            "date": query_date_str,
            "search": "Search"
        }

        try:
            r = requests.post(
                url,
                headers=HEADERS,
                data=payload,
                timeout=15,
                verify=False,  # their SSL cert chain is broken
            )
            if r.status_code != 200:
                return False

            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if table is None:
                return False

            # Check if there's a USD row
            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 6:
                    continue
                code = tds[3].get_text(strip=True).upper()
                if code == "USD":
                    return True

            return False
        except Exception:
            return False

    # 1) Find the last date that actually has data
    real_date = get_last_available_date(exdate, lao_has_data)
    query_date_str = real_date.strftime("%d-%m-%Y")

    # 2) Fetch page for that actual date
    payload = {
        "date": query_date_str,
        "search": "Search"
    }

    r = requests.post(
        url,
        headers=HEADERS,
        data=payload,
        timeout=15,
        verify=False,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Extract displayed date from page (look for "Date: DD-MM-YYYY")
    date_text = None
    for elem in soup.find_all(string=True):
        if "Date:" in elem:
            m = re.search(r"(\d{2}-\d{2}-\d{4})", elem)
            if m:
                date_text = m.group(1)
                break
    if not date_text:
        raise RuntimeError("No 'Date: DD-MM-YYYY' found on page. The page may be empty or the date is invalid.")

    page_date = datetime.strptime(date_text, "%d-%m-%Y").date()
    print(f"Lao page date: {page_date}, requested: {exdate}, effective: {real_date}")

    # Find the table
    table = soup.find("table")
    if table is None:
        raise RuntimeError("No table found on BOL exchange rate page")

    usd_buy = usd_sell = None

    def parse_lao_number(s: str) -> float:
        s = s.strip().replace(".", "").replace(",", ".")  # dot=thousands, comma=decimal
        try:
            return float(s)
        except Exception as e:
            raise ValueError(f"Cannot parse '{s}'") from e

    # Each row: No | Countries | Foreign Currencies | Currency Code | Buy Rates | Sell Rates
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        code = tds[3].get_text(strip=True).upper()

        if code == "USD":
            buy_str = tds[4].get_text(strip=True)
            sell_str = tds[5].get_text(strip=True)

            usd_buy = parse_lao_number(buy_str)
            usd_sell = parse_lao_number(sell_str)
            break

    if usd_buy is None or usd_sell is None:
        codes = [tds[3].get_text(strip=True) for tr in table.find_all("tr")
                 for tds in [tr.find_all("td")] if len(tds) >= 4]
        raise RuntimeError(f"USD row not found. Available currency codes: {codes}")

    mid = (usd_buy + usd_sell) / 2.0

    return [{
        "country": "Lao",
        "unit": "LAK",
        "buy": usd_buy,
        "sell": usd_sell,
        "value": mid,                           # what you asked for
        "date_of_page": exdate.strftime("%Y-%m-%d"),     # actual data date
        "website": url,
        "Source": "Bank of the lao P.D.R",
        "Status": "buy, sell"
    }]