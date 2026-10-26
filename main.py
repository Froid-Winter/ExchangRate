
import argparse
import asyncio
import os
import signal
import time
import traceback
import warnings

import pandas as pd
import urllib3

from datetime import datetime, timezone, date, timedelta

warnings.filterwarnings(
    "ignore",
    category=urllib3.exceptions.InsecureRequestWarning
)

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

SCRAPER_TIMEOUT_SECONDS = 240  # 4 minutes per scraper

SCRAPER_CONFIGS = [
    (
        "imf",
        [
            "Brunei", "China", "India", "Japan", "Malaysia",
            "Philippines", "Saudi Arabia", "Singapore", "Thailand"
        ],
        lambda: scrap_IMF(TARGET_DATE)
    ),
    ("hongkong", ["Hong Kong"], lambda: scrape_hongkong(TARGET_DATE)),
    ("cambodia", ["Cambodia"], lambda: scrape_cambodia(TARGET_DATE)),
    ("laos", ["Laos"], lambda: scrape_lao(TARGET_DATE)),
    ("myanmar", ["Myanmar"], lambda: scrape_myanmar(TARGET_DATE)),
    ("pakistan", ["Pakistan"], lambda: scrape_pakistan(TARGET_DATE)),
    ("vietnam", ["Vietnam"], lambda: scrape_vietnam(TARGET_DATE)),
    # ("sri_lanka", ["Sri Lanka"], lambda: scrape_sri_lanka(TARGET_DATE)),
    ("egypt", ["Egypt"], lambda: egypt_scrape(TARGET_DATE)),
    ("turkey", ["Turkey"], lambda: turkey_scrape(TARGET_DATE)),
    ("indonesia", ["Indonesia"], lambda: indonesia_scrape(TARGET_DATE)),
    # (
    #     "bangladesh",
    #     ["Bangladesh"],
    #     lambda: asyncio.run(scrape_bangladesh(TARGET_DATE))
    # ),
]


# -----------------------
# PER-SCRAPER TIMEOUT
# -----------------------

def timeout_handler(signum, frame):
    raise TimeoutError(
        f"Scraper exceeded {SCRAPER_TIMEOUT_SECONDS} seconds"
    )


def run_with_timeout(func):
    # GitHub Actions uses Linux, where SIGALRM is available.
    # Run this from the main thread.
    if os.name == "nt" or not hasattr(signal, "SIGALRM"):
        return func()

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(SCRAPER_TIMEOUT_SECONDS)

    try:
        return func()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


# -----------------------
# RETRY HELPERS
# -----------------------

def get_existing_countries():
    target_str = str(TARGET_DATE)

    if not os.path.exists(CSV_FILE):
        print(f"CSV does not exist: {CSV_FILE}")
        return set()

    try:
        df = pd.read_csv(CSV_FILE)

        required = {"date_of_page", "country"}
        if not required.issubset(df.columns):
            print(f"CSV missing required columns: {required - set(df.columns)}")
            return set()

        page_dates = pd.to_datetime(
            df["date_of_page"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        existing = set(
            df.loc[page_dates == target_str, "country"]
            .dropna()
            .astype(str)
            .str.strip()
        )

        print(f"Existing countries for {target_str}: {sorted(existing)}")
        return existing

    except Exception:
        print("ERROR reading existing CSV:")
        traceback.print_exc()
        return set()


def get_scrapers_to_run(retry):
    if not retry:
        return [
            (name, func)
            for name, _, func in SCRAPER_CONFIGS
        ]

    existing = get_existing_countries()

    all_countries = {
        country
        for _, countries, _ in SCRAPER_CONFIGS
        for country in countries
    }

    missing = all_countries - existing

    if not missing:
        print(f"All configured countries have data for {TARGET_DATE}.")
        return []

    selected = []

    for name, countries, func in SCRAPER_CONFIGS:
        missing_for_scraper = set(countries) & missing

        if missing_for_scraper:
            print(f"Retrying {name}: {sorted(missing_for_scraper)}")
            selected.append((name, func))

    return selected


# -----------------------
# MAIN PIPELINE
# -----------------------

def main(retry=False):
    print("=" * 60)
    print("ETL PIPELINE START")
    print(f"Target date: {TARGET_DATE}")
    print(f"UTC start: {datetime.now(timezone.utc).isoformat()}")
    print(f"Retry mode: {retry}")
    print(f"CSV path: {CSV_FILE}")
    print("=" * 60)

    scrapers = get_scrapers_to_run(retry)

    if not scrapers:
        print("No scrapers to run.")
        return True

    rows = []
    failed = []
    empty = []

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for name, func in scrapers:
        started = time.monotonic()

        print(f"\n{'=' * 50}")
        print(f"START: {name}")
        print(f"Time: {datetime.now(timezone.utc).isoformat()}")

        try:
            result_list = run_with_timeout(func)

            if not result_list:
                print(f"WARNING: {name} returned no rows.")
                empty.append(name)
                continue

            print(f"{name} returned {len(result_list)} rows.")

            for item in result_list:
                item["date_of_scrape"] = scraped_at
                rows.append(item)

                print(
                    f"{item.get('country')} -> "
                    f"{item.get('value')} ({item.get('unit')})"
                )

        except Exception as exc:
            print(f"ERROR in {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            failed.append(name)

        finally:
            elapsed = time.monotonic() - started
            print(f"FINISHED: {name}; elapsed={elapsed:.1f}s")

    if rows:
        try:
            write_to_csv(rows)
            print(f"Saved {len(rows)} rows to {CSV_FILE}")
        except Exception:
            print("ERROR writing the CSV:")
            traceback.print_exc()
            return False
    else:
        print("No data scraped; CSV was not updated.")

    if empty:
        print(f"SCRAPERS RETURNING NO DATA: {empty}")

    if failed:
        print(f"FAILED SCRAPERS: {failed}")
        return False

    if empty:
        # Empty results may mean a source has not published the target date.
        # Fail the job so the missing result is visible in Actions.
        return False

    print("ETL PIPELINE COMPLETED SUCCESSFULLY")
    return True


# -----------------------
# ENTRY POINT
# -----------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--retry",
        action="store_true",
        help="Only run scrapers for countries missing the target date"
    )

    args = parser.parse_args()
    success = main(retry=args.retry)

    if not success:
        raise SystemExit(1)
