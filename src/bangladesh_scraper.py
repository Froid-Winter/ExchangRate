import asyncio
from datetime import datetime, date, timedelta, timezone
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from normalize.convert import write_to_csv
import sys
sys.stdout.reconfigure(encoding='utf-8')

async def scrape_bangladesh(target_date, max_days_back=3):
    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        page = await browser.new_page()
        try:
            # await page.goto(
            #     "https://www.bb.org.bd/en/index.php/econdata/exchangerate",
            #     wait_until="networkidle"
            # )

            await page.goto(
                "https://www.bb.org.bd/en/index.php/econdata/exchangerate",
                wait_until="domcontentloaded",
                timeout=60000
            )

            days_checked = 0
            current_date = target_date

            while days_checked <= max_days_back:
                fill_month = current_date.strftime("%B, %Y")
                print(f"\nSearching month: {fill_month}")

                # await page.locator("#currencies").select_option(index=2)

                await page.wait_for_selector("#currencies", timeout = 30000)

                await page.select_option("#currencies", label="USD")
                await page.locator("#search-form > div:nth-child(2) > input").fill(fill_month)
                await page.keyboard.press("Enter")
                await page.locator("button:has-text('SEARCH')").click()
                # await page.wait_for_load_state("networkidle")

                await page.wait_for_selector("div.table-wrapper", timeout=30000)

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                table = soup.find("table")

                if not table:
                    current_date = (current_date.replace(day=1) - timedelta(days=1))
                    continue

                rows = table.find_all("tr")[1:]
                for row in rows:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) < 3:
                        continue
                    row_date = datetime.strptime(cols[0], "%d/%m/%y").date()
                    if row_date <= current_date:
                        low = float(cols[1].replace(",", ""))
                        high = float(cols[2].replace(",", ""))
                        mid = (low + high) / 2
                        result = [{
                            "country": "Bangladesh",
                            "value": mid,
                            "unit": "BDT",
                            "website": "https://www.bb.org.bd/en/index.php/econdata/exchangerate",
                            "date_of_page": target_date.strftime("%Y-%m-%d"),
                            "Source": "Bangladesh Bank",
                            "Status": "low, high (avg)"
                        }]
                        # write_to_csv(result)
                        return result

                current_date -= timedelta(days=1)
                days_checked += 1

            return []
        finally:
            await browser.close()

# -------------------
# Run the scraper
# -------------------
if __name__ == "__main__":
    # target_date = adjust_date_bangladesh("2026-03-19")
    target_date = date.today() - timedelta(days=1)
    result = asyncio.run(scrape_bangladesh(target_date))
    print("\nFinal Result:")
    print(result)