import requests
from datetime import datetime, date, timedelta
from dateutil import parser as date_parser
from datetime import timezone
from normalize.holidayhandle import get_last_available_date

def scrape_vietnam(exdate=None):
    """
    Vietnam – SBV reference rate.
    Uses get_last_available_date to walk backwards until a day with data is found.
    """

    # 1) Decide starting date (requested or today)
    if exdate is None:
        start_date_str = datetime.utcnow().strftime("%Y-%m-%d")
    else:
        start_date_str = exdate  # expected 'YYYY-MM-DD'

    BASE_URL = (
        "https://sbv.gov.vn/o/headless-delivery/v1.0/"
        "content-structures/3450514/structured-contents"
    )

    HEADER = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/123.0 Safari/537.36",
        "Accept": "application/json"
    }

    def vietnam_has_data(check_date: date) -> bool:
        """Return True if SBV has any USD rate item for this date."""
        d_str = check_date.strftime("%Y-%m-%d")
        end_str = (check_date + timedelta(days=1)).strftime("%Y-%m-%d")

        url = (
            f"{BASE_URL}"
            f"?filter=datePublished%20ge%20{d_str}T00%3A00%3A00.000Z"
            f"%20and%20datePublished%20le%20{end_str}T00%3A00%3A00.000Z"
        )

        try:
            r = requests.get(url, headers=HEADER, timeout=15)
            if r.status_code != 200:
                return False

            data = r.json()
            items = data.get("items", [])
            if not items:
                return False

            # Optional: check USD exists in at least one item
            for item in items:
                content_fields = item.get("contentFields", [])
                for field in content_fields:
                    if field.get("name") == "tyGiaThamKhaos" and field.get("repeatable"):
                        nested = field.get("nestedContentFields", [])
                        for sub in nested:
                            if (
                                sub.get("name") == "ngoaiTe"
                                and sub.get("contentFieldValue", {}).get("data", "").startswith("USD")
                            ):
                                return True
            return False
        except Exception:
            return False

    # 2) Find the last date with valid USD data
    real_date = get_last_available_date(start_date_str, vietnam_has_data)
    d_str = real_date.strftime("%Y-%m-%d")
    end_date = (real_date + timedelta(days=1)).strftime("%Y-%m-%d")

    url = (
        f"{BASE_URL}"
        f"?filter=datePublished%20ge%20{d_str}T00%3A00%3A00.000Z"
        f"%20and%20datePublished%20le%20{end_date}T00%3A00%3A00.000Z"
    )

    # 3) Fetch actual data for that date
    try:
        r = requests.get(url, headers=HEADER, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"HTTP request failed for Vietnam SBV: {e}")

    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError(f"Failed to parse JSON from SBV: {e}")

    items = data.get("items", [])
    if not items:
        raise RuntimeError(f"No exchange rate items found for Vietnam on {d_str}.")

    item = items[0]
    content_fields = item.get("contentFields", [])

    # Parse reference date & rates
    ref_date = None
    rates = []

    for field in content_fields:
        name = field.get("name")

        if name == "ngayApDung":
            val = field.get("contentFieldValue", {}).get("data")
            if val:
                try:
                    dt = date_parser.isoparse(val)
                    ref_date = dt.astimezone(timezone(timedelta(hours=7))).date()  # ICT
                except Exception:
                    pass  # fallback later

        if name == "tyGiaThamKhaos" and field.get("repeatable"):
            nested = field.get("nestedContentFields", [])
            curr = {}
            for sub in nested:
                n = sub.get("name")
                v = sub.get("contentFieldValue", {}).get("data")
                if n == "ngoaiTe" and v:
                    parts = v.split("-", 1)
                    curr["currency"] = parts[0].strip()
                    curr["name"] = parts[1].strip() if len(parts) > 1 else v
                elif n == "mua":
                    try:
                        curr["buy"] = float(v) if v else 0.0
                    except Exception:
                        curr["buy"] = 0.0
                elif n == "ban":
                    try:
                        curr["sell"] = float(v) if v else 0.0
                    except Exception:
                        curr["sell"] = 0.0
            if curr.get("currency"):
                rates.append(curr)

    if not rates:
        raise RuntimeError("No currency rates extracted from Vietnam SBV contentFields.")

    usd = next((r for r in rates if r["currency"] == "USD"), None)
    if usd is None:
        raise RuntimeError("USD rate not found in Vietnam SBV data.")

    mid = (usd["buy"] + usd["sell"]) / 2.0

    # Prefer ref_date if parsed, otherwise fall back to real_date
    effective_date = (ref_date or real_date).strftime("%Y-%m-%d")

    return [{
        "country": "Vietnam",
        "value": mid,
        "unit": "VND",
        "date_of_page": exdate.strftime("%Y-%m-%d"),             # real SBV rate date
        "website": "https://sbv.gov.vn/vi/t%E1%BB%B7-gi%C3%A1-tham-kh%E1%BA%A3o-gi%E1%BB%AFa-%C4%91%E1%BB%93ng-vi%E1%BB%87t-nam-v%C3%A0-c%C3%A1c-lo%E1%BA%A1i-ngo%E1%BA%A1i-t%E1%BB%87-t%E1%BA%A1i-c%E1%BB%A5c-qu%E1%BA%A3n-l%C3%BD-ngo%E1%BA%A1i-h%E1%BB%91i",
        "Source": "SBV",
        "Status": "buy, sell",
    }]