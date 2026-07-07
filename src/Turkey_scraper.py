import requests
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from normalize.adjustdate import normalize_date
from normalize.holidayhandle import get_last_available_date

def build_tcmb_url(date: datetime):
    year_month = date.strftime("%Y%m")
    day_full = date.strftime("%d%m%Y")
    return f"https://www.tcmb.gov.tr/kurlar/{year_month}/{day_full}.xml"

def turkey_scrape(exdate=None, back_day=5):
    results = []

    exdate = normalize_date(exdate)
    base_date = datetime.combine(exdate, datetime.min.time())

    for i in range(back_day + 1):
        current_date = base_date - timedelta(days=i)
        url = build_tcmb_url(current_date)

        print(f"Checking: {current_date.strftime('%Y-%m-%d')}")
        print(f"URL: {url}")

        try:
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                print("Not found -> go back")
                continue

            # Parse XML
            root = ET.fromstring(response.content)

            currencies = root.findall("Currency")
            if not currencies:
                print("No currency data -> go back")
                continue

            usd_found = False

            for currency in currencies:
                name = currency.findtext("Isim")

                if name and "ABD DOLARI" in name:
                    buy = currency.findtext("BanknoteBuying")
                    sell = currency.findtext("BanknoteSelling")

                    # If data missing -> treat as no data
                    if not buy or not sell:
                        print("USD data missing -> go back")
                        break

                    buy = float(buy)
                    sell = float(sell)
                    mid = (buy + sell) / 2

                    data = {
                        "country": "Turkey",
                        "unit": "TRY",
                        "value": mid,
                        "date_of_page": exdate.strftime("%Y-%m-%d"),
                        "website": url,
                        "Source": "Türkiye Cumhuriyet Merkez Bankası (TCMB)",
                        "Status": "Banknote(buy, sell)",
                    }

                    results.append(data)
                    print(f"USD found: {mid} TRY")
                    return results  # STOP once found

                    usd_found = True

            if not usd_found:
                print("USD not found -> go back")

        except Exception as e:
            print(f"Error: {e} -> go back")

    print("No data found in given range")
    return results