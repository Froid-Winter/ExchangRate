"""Bank Indonesia (BI) USD/IDR transaction rate scraper.

The BI "Transaksi BI" page is an ASP.NET (SharePoint) page.  Its daily
"Search" view only renders a chart for the latest published data, so the
historical rates are fetched through the Time Series view instead:

    Access Data -> Time Series, Currencies -> USD, From/To -> date range

The response embeds the selected series as a JavaScript call:

    renderHighchart2([{"mataUang":"USD  ","beli":...,"jual":...,
                       "TimePeriod":"10/22/2026 12:00:00 AM", ...}, ...])

We parse that array and pick the newest USD entry on/before the target
date (weekends/holidays are skipped automatically).
"""

import json
import os
import re
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from normalize.adjustdate import adjust_date_indonesia, normalize_date

URL = "https://www.bi.go.id/en/statistik/informasi-kurs/transaksi-bi/Default.aspx"

BTN_SEARCH = "btnSearch1"
CURRENCY_SELECT = "ddlmatauang1"
PERIOD_SELECT = "selectPeriod"
# The data call looks like: renderHighchart2([...], 'en');
_SERIES_RE = re.compile(r"renderHighchart2\(\s*(\[.*?\])\s*(?:,[^)]*)?\)", re.S)
_US_DATE_FMT = "%m/%d/%Y %I:%M:%S %p"


def _build_driver():
    options = Options()
    # Headless by default so the scraper also works in CI.  Set
    # HEADLESS=0 (or "false"/"no") to watch the browser.
    headless = os.environ.get("HEADLESS", "1").strip().lower()
    if headless not in ("0", "false", "no", "off"):
        options.add_argument("--headless")
    options.add_argument("--window-size=1400,1000")
    options.set_preference("intl.accept_languages", "en-US,en")
    return webdriver.Firefox(options=options)


def _wait_for_page(driver, wait):
    wait.until(EC.presence_of_element_located((By.ID, PERIOD_SELECT)))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"select[id$='{CURRENCY_SELECT}']")))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id$='txtFrom']")))
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[id$='txtTo']")))


def _submit_range(driver, wait, start_date, end_date):
    """Search the Time Series view for USD between the two dates."""
    driver.get(URL)
    _wait_for_page(driver, wait)

    # Switch the "Access Data" dropdown to the Time Series (range) view.
    driver.execute_script(
        "var s = document.getElementById(arguments[0]);"
        "s.value = 'range';"
        "s.dispatchEvent(new Event('change', {bubbles: true}));",
        PERIOD_SELECT,
    )

    # Select USD in the currencies dropdown.
    driver.execute_script(
        "var s = document.querySelector(\"select[id$='\" + arguments[0] + \"']\");"
        "for (var i = 0; i < s.options.length; i++) {"
        "  if (s.options[i].value.trim().toUpperCase() === 'USD') {"
        "    s.selectedIndex = i; break;"
        "  }"
        "}"
        "s.dispatchEvent(new Event('change', {bubbles: true}));",
        CURRENCY_SELECT,
    )

    # The inputs reject keyboard input, so set them directly through JS.
    driver.execute_script(
        "document.getElementById('txtFrom').value = arguments[0];"
        "document.getElementById('txtTo').value = arguments[1];",
        adjust_date_indonesia(start_date),
        adjust_date_indonesia(end_date),
    )

    # The button can be covered by styled selects, so use a JS click (its
    # inline/jQuery handlers still run).
    button = driver.find_element(By.CSS_SELECTOR, f"input[id$='{BTN_SEARCH}']")
    driver.execute_script("arguments[0].click();", button)

    # The series is embedded in the response as renderHighchart2([...]).
    wait.until(lambda d: _SERIES_RE.search(d.page_source) is not None)


def _extract_usd_series(html):
    """Return [(date, buy, sell), ...] parsed from the embedded series."""
    matches = _SERIES_RE.findall(html)
    if not matches:
        return []

    payload = max(matches, key=len)
    try:
        data = json.loads(payload)
    except ValueError:
        return []

    series = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("mataUang", "").strip().upper() != "USD":
            continue

        try:
            rate_date = datetime.strptime(item["TimePeriod"], _US_DATE_FMT).date()
        except (KeyError, TypeError, ValueError):
            continue

        try:
            buy = float(item.get("beli") or 0)
            sell = float(item.get("jual") or 0)
        except (TypeError, ValueError):
            continue

        if buy > 0 and sell > 0:
            series.append((rate_date, buy, sell))

    series.sort(key=lambda entry: entry[0])
    return series


def indonesia_scrape(exdate=None, back_day=10):
    """Scrape the USD/IDR Bank Indonesia transaction rate.

    Looks back up to ``back_day`` days from ``exdate`` so weekends and
    holidays resolve to the last published business day.  ``date_of_page``
    is kept as the requested date, matching the other scrapers in this
    repository.  Returns ``[]`` when no rate can be found.
    """
    target = normalize_date(exdate)
    start = target - timedelta(days=back_day)

    driver = _build_driver()
    wait = WebDriverWait(driver, 40)

    try:
        print(f"Indonesia: searching {start} .. {target}")
        _submit_range(driver, wait, start, target)
        series = _extract_usd_series(driver.page_source)

        if not series:
            # A short window can be empty around long holidays; retry once
            # with a wider range before giving up.
            wider_start = target - timedelta(days=max(back_day, 30))
            print(f"Indonesia: no data in window, retrying {wider_start} .. {target}")
            _submit_range(driver, wait, wider_start, target)
            series = _extract_usd_series(driver.page_source)

        eligible = [entry for entry in series if entry[0] <= target]
        if not eligible:
            print(f"Indonesia: no USD rate found on or before {target}")
            return []

        rate_date, buy, sell = eligible[-1]
        mid = (buy + sell) / 2.0
        print(
            f"Indonesia: USD {rate_date} -> buy {buy}, sell {sell}, mid {mid}"
        )

        return [{
            "country": "Indonesia",
            "value": mid,
            "unit": "IDR",
            "Sell_Rate": sell,
            "Buy_Rate": buy,
            "date_of_page": target.strftime("%Y-%m-%d"),
            "website": URL,
            "Source": "bank indonesia, bank sentral republik indonesia",
            "Status": "buy, sell",
        }]

    except Exception as e:
        print(f"Indonesia scraper error: {e}")
        return []

    finally:
        try:
            driver.quit()
        except Exception:
            pass
