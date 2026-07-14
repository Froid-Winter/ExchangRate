import argparse
import warnings
import urllib3
import asyncio
import os
import pandas as pd
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, timezone, date, timedelta

from normalize.adjustdate import normalize_date
from normalize.convert import write_to_csv, CSV_FILE

from src.imf_scraper import scrap_IMF
from src.hongkong_scraper import scrape_hongkong
from src.cambodia_scraper import scrape_cambodia
from src.laos_scraper import scrape_lao
from src.myanmar_scraper import scrape_myanmar
from src.pakistan_scraper import scrape_pakistan
from src.veitname_scraper import scrape_vietnam
from src.sri_lanka_scraper import scrape_sri_lanka
from src.egypt_scraper import egypt_scrape
from src.Turkey_scraper import turkey_scrape
from src.indonesia_scraper import indonesia_scrape
from src.bangladesh_scraper import scrape_bangladesh

# -----------------------
# CONFIG
# -----------------------
TARGET_DATE = normalize_date(date.today() - timedelta(days=1))

SCRAPER_CONFIGS = [
    ("imf", ["Brunei", "China", "India", "Japan", "Malaysia", "Philippines", "Saudi Arabia", "Singapore", "Thailand"],
     lambda: scrap_IMF(TARGET_DATE)),
    ("hongkong", ["Hong Kong"], lambda: scrape_hongkong(TARGET_DATE)),
    ("cambodia", ["Cambodia"], lambda: scrape_cambodia(TARGET_DATE)),
    ("laos", ["Laos"], lambda: scrape_lao(TARGET_DATE)),
    ("myanmar", ["Myanmar"], lambda: scrape_myanmar(TARGET_DATE)),
    ("pakistan", ["Pakistan"], lambda: scrape_pakistan(TARGET_DATE)),
    ("vietnam", ["Vietnam"], lambda: scrape_vietnam(TARGET_DATE)),
    ("sri_lanka", ["Sri Lanka"], lambda: scrape_sri_lanka(TARGET_DATE)),
    ("egypt", ["Egypt"], lambda: egypt_scrape(TARGET_DATE)),
    ("turkey", ["Turkey"], lambda: turkey_scrape(TARGET_DATE)),
    ("indonesia", ["Indonesia"], lambda: indonesia_scrape(TARGET_DATE)),
    ("bangladesh", ["Bangladesh"], lambda: asyncio.run(scrape_bangladesh(TARGET_DATE))),
]


def get_existing_countries():
    target_str = TARGET_DATE.strftime("%Y-%m-%d")
    if not os.path.exists(CSV_FILE):
        return set()
    try:
        df = pd.read_csv(CSV_FILE)
        existing = set(df[df["date_of_page"] == target_str]["country"].unique())
        return existing
    except Exception:
        return set()


def get_scrapers_to_run(retry):
    if not retry:
        return [(name, func) for name, _, func in SCRAPER_CONFIGS]

    existing = get_existing_countries()
    all_countries = set()
    for _, countries, _ in SCRAPER_CONFIGS:
        all_countries.update(countries)

    missing = all_countries - existing
    if not missing:
        print(f"All countries have data for {TARGET_DATE}. Nothing to retry.")
        return []

    to_run = []
    for name, countries, func in SCRAPER_CONFIGS:
        countries_set = set(countries)
        if countries_set & missing:
            to_run.append((name, func))
            print(f"  Will retry {name}: missing {countries_set & missing}")

    return to_run


# -----------------------
# MAIN PIPELINE
# -----------------------
def main(retry=False):
    scrapers = get_scrapers_to_run(retry)

    if not scrapers:
        print("No scrapers to run.")
        return

    rows = []
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for name, func in scrapers:
        try:
            result_list = func()

            if not result_list:
                continue

            for item in result_list:
                item["date_of_scrape"] = scraped_at
                rows.append(item)

                print(f"{item['country']} -> {item['value']} ({item['unit']})")

        except Exception as e:
            print(f"ERROR in {name}: {e}")

    if not rows:
        print("No data scraped.")
        return

    write_to_csv(rows)
    print(f"Saved {len(rows)} rows")


# -----------------------
# ENTRY POINT
# -----------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--retry", action="store_true", help="Only scrape countries missing data for target date")
    args = parser.parse_args()
    main(retry=args.retry)