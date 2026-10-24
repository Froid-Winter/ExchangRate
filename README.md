# Exchange Rates

This project collects daily exchange-rate data for selected countries from the
International Monetary Fund and national sources. The Python pipeline targets
the previous day's rates, normalizes the results, and stores them in
[`data/raw/ExchangeRates.csv`](data/raw/ExchangeRates.csv).

## Countries

The enabled scrapers cover Brunei, Cambodia, China, Egypt, Hong Kong, India,
Indonesia, Japan, Laos, Malaysia, Myanmar, Pakistan, the Philippines, Saudi
Arabia, Singapore, Sri Lanka, Thailand, Turkey, and Vietnam. Rates may not be
available for every country or date, depending on the source.

The Bangladesh scraper is present in the codebase but is currently disabled in the main pipeline due to the website under maintenance. "The Service is under Maintenance"

## Requirements

- Python 3.9 (the version used by the GitHub Actions workflow)
- Firefox and geckodriver for the Firefox-based scrapers (IMF, Egypt, and
  Indonesia)

Install the Python dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

Make sure Firefox and geckodriver are installed and available to Selenium if
you want to run all enabled scrapers. The GitHub Actions workflow configures
these dependencies for its scheduled runs.

## Run

Run all enabled scrapers for the previous day:

```bash
python main.py
```

Retry scrapers for countries that do not yet have a CSV entry for the target
date:

```bash
python main.py --retry
```

The retry mode checks each country's `date_of_page` against the target date and
runs the corresponding scraper when data is missing. The result is appended to
the CSV; duplicate rows for the same country and page date are replaced with
the latest result.

## Output

The CSV contains these columns:

| Column | Description |
| --- | --- |
| `country` | Country or territory |
| `value` | Reported exchange-rate value |
| `unit` | Currency unit associated with the value |
| `website` | Source page or report URL |
| `date_of_page` | Date the reported rate applies to |
| `date_of_scrape` | Date the pipeline collected the data |
| `Source` | Publisher or data source |
| `Status` | Rate status or type, when provided by the source |

## Automation

GitHub Actions runs the pipeline daily at 05:00 UTC and retries missing
countries at 08:00 UTC. You can also start the workflow manually from the
repository's **Actions** tab. Successful changes to the CSV are committed by
the workflow.
