import warnings
import urllib3
import asyncio
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, timezone, date, timedelta

from normalize.adjustdate import normalize_date
from normalize.convert import write_to_csv

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


# -----------------------
# MAIN PIPELINE
# -----------------------
def main():
    scraper_functions = [
        lambda: scrap_IMF(TARGET_DATE),
        lambda: scrape_hongkong(TARGET_DATE),
        lambda: scrape_cambodia(TARGET_DATE),
        lambda: scrape_lao(TARGET_DATE),
        lambda: scrape_myanmar(TARGET_DATE),
        lambda: scrape_pakistan(TARGET_DATE),
        lambda: scrape_vietnam(TARGET_DATE),
        lambda: scrape_sri_lanka(TARGET_DATE),
        lambda: egypt_scrape(TARGET_DATE),
        lambda: turkey_scrape(TARGET_DATE),
        lambda: indonesia_scrape(TARGET_DATE),
        lambda: asyncio.run(scrape_bangladesh(TARGET_DATE)),
    ]

    rows = []
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for func in scraper_functions:
        try:
            result_list = func()

            if not result_list:
                continue

            for item in result_list:
                item["date_of_scrape"] = scraped_at
                rows.append(item)

                print(f"{item['country']} -> {item['value']} ({item['unit']})")

        except Exception as e:
            print(f"ERROR in {func.__name__}: {e}")

    if not rows:
        print("No data scraped.")
        return

    write_to_csv(rows)
    print(f"Saved {len(rows)} rows")


# -----------------------
# ENTRY POINT
# -----------------------
if __name__ == "__main__":
    main()