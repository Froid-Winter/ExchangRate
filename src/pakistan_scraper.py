import requests
from datetime import datetime, date
from io import BytesIO
from pdfminer.high_level import extract_text
from normalize.adjustdate import normalize_date, _is_number_line
from normalize.holidayhandle import get_last_available_date

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

def scrape_pakistan(exdate=None):
    base_url = "https://www.nbp.com.pk/RateSheetFiles"

    # --- 1. Choose starting date (requested or today) as YYYY-MM-DD string ---
    if exdate is None:
        start_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        start_date_str = exdate  # expected 'YYYY-MM-DD'

    # --- 2. Define "has data" checker for a given date ---
    def pakistan_has_data(check_date: date) -> bool:
        dt_for_pdf = check_date.strftime("%d-%m-%Y")  # dd-mm-yyyy
        url = f"{base_url}/NBP-RateSheet-{dt_for_pdf}.pdf"

        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                return False

            pdf_text = extract_text(BytesIO(r.content))
            # Simple sanity check: file exists and mentions US DOLLAR
            return "US DOLLAR" in pdf_text.upper()
        except Exception:
            return False

    # --- 3. Find last date where the PDF exists and has USD data ---
    real_date = get_last_available_date(start_date_str, pakistan_has_data)
    dt_for_pdf  = real_date.strftime("%d-%m-%Y")   # for PDF filename
    dt_for_page = real_date.strftime("%Y-%m-%d")   # stored in Excel / output

    url = f"{base_url}/NBP-RateSheet-{dt_for_pdf}.pdf"

    # --- 4. Fetch PDF for the actual (holiday-adjusted) date ---
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    pdf_text = extract_text(BytesIO(r.content))
    lines = [ln.strip() for ln in pdf_text.splitlines() if ln.strip()]

    # --- 5. Find 'US DOLLAR' line index ---
    usd_idx = None
    for i, ln in enumerate(lines):
        if "US DOLLAR" in ln.upper():
            usd_idx = i
            break

    if usd_idx is None:
        raise ValueError(f"'US DOLLAR' not found in NBP PDF for {dt_for_page}")

    # --- 6. Scan forward for numeric lines and collect them ---
    numeric_vals = []
    for ln in lines[usd_idx + 1 :]:
        if _is_number_line(ln):
            val = float(ln.replace(",", ""))
            numeric_vals.append(val)
            if len(numeric_vals) > 38:
                break

    if len(numeric_vals) < 39:
        raise ValueError(
            f"Not enough numeric rates found after USD row. "
            f"Found {len(numeric_vals)} numbers: {numeric_vals}"
        )

    # Your existing logic: buy = numeric_vals[38]
    buy = numeric_vals[38]
    sell = numeric_vals[25]
    mid = (buy + sell) / 2.0

    return [{
        "country": "Pakistan",
        "value": mid,                      # update
        "unit": "PKR",                     # 1 USD = X PKR
        "date_of_page": exdate.strftime("%Y-%m-%d"),       # actual date of the PDF / rate
        "website": url,
        "Source": "National Bank of Pakistan",
        "Status": "buy",
    }]