import time as time_module
from datetime import datetime, timedelta
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException
from normalize.adjustdate import adjust_date_egypt, normalize_date

def egypt_scrape(exdate=None, back_day=10):
    options = Options()
    options.add_argument("--headless")  # Uncomment for headless mode
    driver = webdriver.Firefox(options=options)
    wait = WebDriverWait(driver, 20)
    results = []

    try:
        # Parse the target date
        target_date = adjust_date_egypt(exdate)
        print(f"Target date: {target_date}")

        # Get base date for calculations
        exdate = normalize_date(exdate)
        base_date = datetime.combine(exdate, datetime.min.time())

        # Navigate to the main page
        url = "https://www.cbe.org.eg/en/economic-research/statistics/cbe-exchange-rates/historical-data"
        print(f"Navigating to: {url}")
        driver.get(url)

        time_module.sleep(5)  # Give more time for page to load

        # Wait for page to fully load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Wait for the form to load
        wait.until(EC.presence_of_element_located((By.ID, "historicalDataForm")))

        # Iterate back through days to find data
        for days_back in range(back_day + 1):
            # Calculate date for this iteration
            current_date = base_date - timedelta(days=days_back)
            year = current_date.year
            month = current_date.strftime("%m")  # Month as number (01-12)
            month_name = current_date.strftime("%B")  # Full month name
            day = current_date.day

            current_date_str = f"{day:02d}/{month}/{year}" # Format: 01/02/2026

            print(f"\nAttempting to select date: {current_date_str}")

            try:
                # Function to set date using JavaScript (cleaner approach)
                def set_date_via_javascript(element_id, date_str):
                    """Set date directly via JavaScript"""
                    js_script = f"""
                    document.getElementById("{element_id}").value = "{date_str}";
                    // Trigger change event
                    var event = new Event('change', {{ bubbles: true }});
                    document.getElementById("{element_id}").dispatchEvent(event);
                    """
                    driver.execute_script(js_script)
                    time_module.sleep(1)
                    print(f"Set {element_id} to {date_str}")

                # Set From Date
                set_date_via_javascript("fromDate", current_date_str)

                # Set To Date (same date for single day)
                set_date_via_javascript("toDate", current_date_str)

                # Handle the "Select Option" dropdown - This is a button that opens a multiselect popup
                print("Handling currency selection dropdown...")

                # First, click the "Select Option" button to open the popup
                try:
                    select_option_button = driver.find_element(By.XPATH, '//*[@id="multipleSelectID_ms"]/span[1]/img')
                    print("Found 'Select Option' button")

                    # Scroll to the button
                    # driver.execute_script("arguments[0].scrollIntoView(true);", select_option_button)
                    time_module.sleep(1)
                    select_option_words = driver.find_element(By.XPATH, '//*[@id="multipleSelectID_ms"]/span[2]')
                    select_words = select_option_words.text.strip()
                    print(f"we have: {select_words}")
                    if select_words == "Select Option":
                        # Click to open the multiselect popup
                        select_option_button.click()

                        print("Clicked 'Select Option' button to open popup")
                        time_module.sleep(2)

                        try:
                            select_usd = driver.find_element(By.XPATH, '//*[@id="ui-multiselect-0-multipleSelectID-option-0"]')
                            print(f"Found USD option with text: {select_usd.text}")
                            select_usd.click()
                            print("Clicked USD option to select it")


                        except Exception as popup_error:
                            print(f"Multiselect popup didn't appear: {popup_error}")

                    else:
                        print(f"We already select currency: '{select_words}'")

                except Exception as button_error:
                    print(f"Could not click 'Select Option' button: {button_error}")

                # Click the Show Data button
                try:
                    # Find the show button
                    show_button = driver.find_element(By.ID, "btnsubmit")

                    # Scroll to button
                    driver.execute_script("arguments[0].scrollIntoView(true);", show_button)
                    time_module.sleep(1)

                    # Click using JavaScript (more reliable)
                    driver.execute_script("arguments[0].click();", show_button)
                    print("Show button clicked")

                    # Wait for results
                    print("Waiting for results...")
                    time_module.sleep(5)

                    # Check if there's data in the table
                    try:
                        # Look for the data table
                        table_selectors = [
                            (By.CLASS_NAME, "dynamic-data-table"),
                            (By.CLASS_NAME, "data-table"),
                            (By.TAG_NAME, "table"),
                            (By.XPATH, '//table[contains(@class, "table")]'),
                            (By.XPATH, '//div[contains(@class, "table-responsive")]//table')
                        ]

                        table = None
                        for selector_type, selector_value in table_selectors:
                            try:
                                table = driver.find_element(selector_type, selector_value)
                                if table.is_displayed():
                                    break
                            except:
                                continue

                        if table:
                            rows = table.find_elements(By.TAG_NAME, "tr")
                            print(f"Found table with {len(rows)} rows")

                            if len(rows) > 1:  # Has data (header + at least one row)
                                print(f"Found data for {current_date_str}")

                                # Parse the table data
                                for i in range(1, len(rows)):
                                    cols = rows[i].find_elements(By.TAG_NAME, "td")
                                    if len(cols) >= 3:
                                        got_date = cols[0].text.strip()
                                        print(f"Row {i}: got_date={got_date}")
                                        buy = cols[2].text.strip()
                                        sell = cols[3].text.strip()
                                        rate = (float(buy) + float(sell)) / 2
                                        if got_date == current_date_str:
                                            results.append({
                                                "country": "Egypt",
                                                "unit": "EGP",
                                                'date_of_page': exdate.strftime("%Y-%m-%d"),
                                                'website': url,
                                                "value": rate,
                                                "Source": "Central bank of Egypt (CBE)",
                                                "Status": "buy sell",
                                            })

                                if results:  # If we found data, break
                                    print(f"Successfully collected {len(results)} records")
                                    break
                            else:
                                print(f"Table found but no data rows for {current_date_str}")

                        else:
                            print(f"No table found for {current_date_str}")

                    except NoSuchElementException:
                        print(f"No table found for {current_date_str}")

                    except Exception as e:
                        print(f"Error parsing table: {e}")

                except Exception as button_error:
                    print(f"Error with show button: {button_error}")

            except Exception as e:
                print(f"Error processing date {current_date_str}: {str(e)[:100]}")
                continue

    except Exception as e:
        print(f"General error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()

    return results