import os
import pandas as pd
from datetime import datetime, timezone

CSV_FILE = os.path.join("data", "raw", "ExchangeRates.csv")

def write_to_csv(data):
    try:
        columns = [
            "country", "value", "unit",
            "website", "date_of_page",
            "date_of_scrape", "Source", "Status"
        ]

        # Ensure date_of_scrape is set (fallback in case caller didn't set it)
        scrape_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for row in data:
            row.setdefault("date_of_scrape", scrape_date)

        # Read existing CSV if exists
        if os.path.exists(CSV_FILE):
            df = pd.read_csv(CSV_FILE)
        else:
            df = pd.DataFrame(columns=columns)

        # New data
        new_df = pd.DataFrame(data, columns=columns)

        # Append
        if df.empty:
            df = new_df
        else:
            df = pd.concat([df, new_df], ignore_index=True)

        # Remove duplicates
        df = df.drop_duplicates(subset=["country", "date_of_page"], keep="last")

        # Save to CSV
        df.to_csv(CSV_FILE, index=False)

    except Exception as e:
        print(f"Error writing CSV: {e}")