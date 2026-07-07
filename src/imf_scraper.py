from selenium.webdriver.firefox.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from normalize.adjustdate import normalize_date, last_day_of_month, is_missing
from dateutil import parser as date_parser
from datetime import datetime, date, timedelta
import pandas as pd
import time as time_module

def scrap_IMF(exdate=None, max_months_back=12):
    """
    Scrape IMF exchange rate data for specified countries

    Args:
        exdate: Target date for data (string in 'YYYY-MM-DD' format, datetime, or date object)
        max_months_back: Maximum number of months to go back if data not found

    Returns:
        List of dictionaries with exchange rate data
    """
    countries_map = {
        "Brunei": "Brunei dollar",
        "China": "Chinese yuan",
        "India": "Indian rupee",
        "Japan": "Japanese yen",
        "Malaysia": "Malaysian ringgit",
        "Philippines": "Philippine peso",
        "Saudi Arabia": "Saudi Arabian riyal",
        "Singapore": "Singapore dollar",
        "Thailand": "Thai baht",
    }

    options = Options()
    options.add_argument("--headless")  # Uncomment for headless mode
    driver = webdriver.Firefox(options=options)
    results = []

    try:
        # Parse the target date
        target_date = normalize_date(exdate)
        print(f"Target date: {target_date.strftime('%Y-%m-%d')}")

        # Iterate back through months to find data
        for months_back in range(max_months_back + 1):
            # Calculate month and year for URL generation
            months_to_subtract = months_back
            year = target_date.year
            month = target_date.month - months_to_subtract

            # Adjust year if month goes below 1
            while month < 1:
                month += 12
                year -= 1

            # Get the last day of that month for URL
            url_date = last_day_of_month(date(year, month, 1))

            url = f"https://www.imf.org/external/np/fin/data/rms_mth.aspx?SelectDate={url_date:%Y-%m-%d}&reportType=REP"

            print(f"Checking IMF data for month ending: {url_date.strftime('%B %d, %Y')}")
            driver.get(url)
            time_module.sleep(3)

# ===============================================================
            # Handle access denied retries
            for attempt in range(4):
                if "Access Denied" in driver.title or "Access Denied" in driver.page_source:
                    print(f"   Access Denied detected (attempt {attempt + 1}/4), waiting and retrying...")
                    driver.refresh()
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time_module.sleep(5)
                else:
                    break
# ===============================================================

            # Try to find and extract table data
            try:
                # Extract headers
                h1_elements = driver.find_elements(By.XPATH, '//*[@id="content"]/center/table[2]/tbody/tr[2]/td/div/center/table/tbody/tr[2]/th')
                h2_elements = driver.find_elements(By.XPATH, '//*[@id="content"]/center/table[2]/tbody/tr[3]/td/div/center/table/tbody/tr[2]/th')

                headers = [h.text.strip() for h in h1_elements] + [h.text.strip() for h in h2_elements][1:]

                # Extract data rows
                all_data_rows = []
                for r in range(3, 39):
                    try:
                        t1_cols = driver.find_elements(By.XPATH, f'//*[@id="content"]/center/table[2]/tbody/tr[2]/td/div/center/table/tbody/tr[{r}]/td')
                        t2_cols = driver.find_elements(By.XPATH, f'//*[@id="content"]/center/table[2]/tbody/tr[3]/td/div/center/table/tbody/tr[{r}]/td')

                        if t1_cols:
                            data1 = [c.text.strip() for c in t1_cols]
                            data2 = [c.text.strip() for c in t2_cols][1:] if t2_cols else []
                            full_row = data1 + data2
                            all_data_rows.append(full_row)
                    except NoSuchElementException:
                        continue  # Skip rows that don't exist

                # Check if we got valid data
                if all_data_rows and len(headers) > 0:
                    df = pd.DataFrame(all_data_rows, columns=headers)

                    print(f"   Found table with {len(df)} rows and {len(df.columns)} columns")

                    # Parse all date headers to find available dates
                    available_dates = []
                    for idx, header in enumerate(headers):
                        if idx == 0:  # Skip "Currency" column
                            continue

                        clean_header = header.replace('\n', ' ').strip()

                        # Try to parse date from header
                        try:
                            header_date = date_parser.parse(clean_header, fuzzy=True).date()
                            available_dates.append((idx, header_date, clean_header))
                        except Exception as e:
                            continue

                    if not available_dates:
                        print(f"   No parseable date columns found")
                        continue

                    # Sort dates in descending order (most recent first)
                    available_dates.sort(key=lambda x: x[1], reverse=True)

                    # NEW LOGIC: For each country, try dates in order until we find valid data
                    # We'll collect data for each country separately
                    country_data = {}

                    # Process each country
                    for country, currency in countries_map.items():
                        currency_code = currency.split()[-1]

                        # Try each date from most recent to oldest
                        for idx, header_date, clean_header in available_dates:
                            # Only consider dates on or before target_date
                            if header_date > target_date:
                                continue

                            found_data = False
                            exchange_rate = None

                            # Search for this country in the rows
                            for _, row in df.iterrows():
                                country_cell = str(row.iloc[0]).lower()

                                # Check if country or currency name appears in the cell
                                if (country.lower() in country_cell or
                                    currency.lower() in country_cell):

                                    # Get exchange rate value for this date
                                    exchange_rate = row.iloc[idx]

                                    # Check if value is missing
                                    if is_missing(exchange_rate):
                                        # Try next older date
                                        break

                                    # Clean the exchange rate value
                                    try:
                                        rate_str = str(exchange_rate).strip()
                                        # Remove any non-numeric characters except decimal point
                                        rate_clean = ''.join(c for c in rate_str if c.isdigit() or c == '.' or c == '-')
                                        if rate_clean and rate_clean != '-':
                                            exchange_rate = float(rate_clean)
                                            found_data = True
                                    except (ValueError, AttributeError):
                                        # If conversion fails, try next date
                                        break

                                    if found_data:
                                        country_data[country] = {
                                            "country": country,
                                            "unit": currency_code,
                                            "value": exchange_rate,
                                            "date_of_page(origine)": header_date.strftime("%Y-%m-%d"),
                                            "date_of_page": exdate.strftime("%Y-%m-%d"),
                                            "scrape_date": target_date.strftime("%Y-%m-%d"),
                                            "Status": "Mid-point",
                                            "website": url,
                                            "Source": "IMF",
                                        }
                                        print(f"   {country}: {exchange_rate} {currency_code} on {header_date}")
                                        break

                            if found_data:
                                break  # Found data for this country, move to next country

                    # Convert country_data dict to list
                    filtered_data = list(country_data.values())

                    if filtered_data:
                        results.extend(filtered_data)

                        # Check if we found all countries
                        found_countries = set(country_data.keys())
                        if len(found_countries) == len(countries_map):
                            print(f"   Found all {len(countries_map)} countries")
                            break  # Stop searching if we found all countries
                        else:
                            missing = set(countries_map.keys()) - found_countries
                            print(f"   Missing {len(missing)} countries: {', '.join(missing)}")
                            print(f"   Continuing to search older months...")
                    else:
                        print(f"   No data found for any countries in this month")

                else:
                    print(f"   No data table found or empty table")

            except NoSuchElementException as e:
                print(f"   Table structure not found: {str(e)}")
                continue
            except Exception as e:
                print(f"   Error processing table: {str(e)}")
                continue

        print(f"\nTotal results found: {len(results)}")
        if results:
            # Sort results by country for consistent output
            results.sort(key=lambda x: x['country'])
            print("Collected data:")
            for result in results:
                if result['date_of_page(origine)'] == result['scrape_date']:
                    print(f"  {result['date_of_page(origine)']}: {result['country']} - {result['value']} {result['unit']}")
                else:
                    print(f"  {result['date_of_page(origine)']}: {result['country']} - {result['value']} {result['unit']} (requested: {result['scrape_date']})")

            # Show summary
            exact_matches = sum(1 for r in results if r['date_of_page(origine)'] == r['scrape_date'])
            fallbacks = len(results) - exact_matches
            print(f"\nSummary: {exact_matches} exact matches, {fallbacks} fallback dates")
        else:
            print("No data found for the specified date or any previous dates")

    except Exception as e:
        print(f"Critical error: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()

    return results