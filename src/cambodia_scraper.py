from bs4 import BeautifulSoup
from normalize.adjustdate import normalize_date
import requests
from datetime import datetime, date, timedelta

def fetch_month_data(target):
    """Fetch table data for a given month"""
    url = f"https://www.tax.gov.kh/en/exchange-rate?for_year={target.year}&for_month={target.month:02d}"
    # print(f"Fetching: {url}")

    response = requests.get(url, verify=False)
    soup = BeautifulSoup(response.content, "html.parser")

    table = soup.find("table", {"class": "table"})
    if not table:
        return []

    rows = table.find_all("tr")
    results = []

    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) >= 3:
            try:
                row_date = datetime.strptime(cols[0].text.strip(), "%B %d, %Y").date()
            except:
                continue

            results.append({
                "date": row_date,
                "unit": cols[1].text.strip(),
                "rate": cols[2].text.strip(),
                "source": cols[3].text.strip() if len(cols) > 3 else "N/A"
            })

    return results

def scrape_cambodia(exdate=None, max_back_days=5):
    target = normalize_date(exdate)

    for i in range(max_back_days):
        current_date = target - timedelta(days=i)

        # fetch data for that month
        month_data = fetch_month_data(current_date)

        # find exact match
        for row in month_data:
            if row["date"] == current_date:
                return [{
                    "country": "Cambodia",
                    "value": row["rate"],
                    "unit": "KHR",
                    "date_of_page": exdate.strftime("%Y-%m-%d"),
                    "website": f"https://www.tax.gov.kh/en/exchange-rate?for_year={current_date.year}&for_month={current_date.month:02d}",
                    "Source": row["source"],
                    "Status": "Official Rate Riel",
                }]

    raise ValueError(f"No data found within {max_back_days} days")