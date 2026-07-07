from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import time as time_module
from normalize.adjustdate import adjust_date_indonesia, normalize_date


def indonesia_scrape(exdate=None, back_day=10):
    options = Options()
    options.add_argument("--headless")  # Uncomment for headless mode
    driver = webdriver.Firefox(options=options)
    wait = WebDriverWait(driver, 10)
    results = []

    try:
        # Parse the target date
        target_date = adjust_date_indonesia(exdate)
        print(f"Target date: {target_date}")

        # Get base date for calculations
        exdate = normalize_date(exdate)
        base_date = datetime.combine(exdate, datetime.min.time())

        # Iterate back through days to find data
        for days_back in range(back_day + 1):
            # Calculate date for this iteration
            current_date = base_date - timedelta(days=days_back)
            formatted_date = adjust_date_indonesia(current_date.strftime("%Y-%m-%d"))

            url = f"https://www.bi.go.id/en/statistik/informasi-kurs/transaksi-bi/Default.aspx"

            print(f"Checking Indonesia data for date: {formatted_date}")
            driver.get(url)
            time_module.sleep(2)

            # Try to find and extract table data
            try:
                # Wait for the page to load
                time_module.sleep(2)

                # Method 1: Try JavaScript to set the date directly
                try:
                    driver.execute_script(
                        f"document.getElementById('ctl00_PlaceHolderMain_g_6c89d4ad_107f_437d_bd54_8fda17b556bf_ctl00_txtTanggal').value = '{formatted_date}';"
                    )
                    print(f"Date set via JavaScript: {formatted_date}")
                except Exception as js_error:
                    print(f"JavaScript date setting failed: {js_error}")

                    # Method 2: Try using the date picker instead of direct input
                    try:
                        # Click the date input field first
                        date_input = wait.until(EC.element_to_be_clickable(
                            (By.XPATH, '//*[@id="ctl00_PlaceHolderMain_g_6c89d4ad_107f_437d_bd54_8fda17b556bf_ctl00_txtTanggal"]')
                        ))

                        # Scroll into view
                        driver.execute_script("arguments[0].scrollIntoView(true);", date_input)
                        time_module.sleep(1)

                        # Clear using JavaScript
                        driver.execute_script("arguments[0].value = '';", date_input)

                        # Click and send keys
                        date_input.click()
                        time_module.sleep(0.5)

                        # Send keys slowly
                        for char in formatted_date:
                            date_input.send_keys(char)
                            time_module.sleep(0.1)

                        print(f"Date set via direct input: {formatted_date}")
                    except Exception as e:
                        print(f"Direct input also failed: {e}")
                        continue

                # Click search button
                try:
                    search_button = wait.until(EC.element_to_be_clickable(
                        (By.ID, "ctl00_PlaceHolderMain_g_6c89d4ad_107f_437d_bd54_8fda17b556bf_ctl00_btnSearch2")
                    ))
                    search_button.click()
                    print("Search button clicked")
                except Exception as e:
                    # Try alternative click method
                    try:
                        driver.execute_script(
                            "document.getElementById('ctl00_PlaceHolderMain_g_6c89d4ad_107f_437d_bd54_8fda17b556bf_ctl00_btnSearch2').click();"
                        )
                        print("Search button clicked via JavaScript")
                    except Exception as js_click_error:
                        print(f"Search button click failed: {js_click_error}")
                        continue

                # Wait for results to load
                time_module.sleep(3)

                # Try to find the results table
                try:
                    # Wait for table to load
                    table = wait.until(EC.presence_of_element_located(
                        (By.XPATH, '//*[@id="ctl00_PlaceHolderMain_g_6c89d4ad_107f_437d_bd54_8fda17b556bf_ctl00_gvSearchResult2"]')
                    ))

                    # Extract table data
                    rows = table.find_elements(By.TAG_NAME, "tr")

                    if len(rows) > 1:  # If we have data rows
                        # Extract data from table
                        for row in rows[1:]:  # Skip header row
                            cols = row.find_elements(By.TAG_NAME, "td")
                            if len(cols) >= 4 and cols[0].text.strip() == "USD":
                                sell = cols[2].text.strip().replace(',', '')
                                buy = cols[3].text.strip().replace(',', '')

                                if sell and buy and sell != '0' and buy != '0':
                                    # Calculate rate (midpoint or whatever logic you need)
                                    # You might want to adjust this calculation
                                    sell_rate = float(sell)
                                    buy_rate = float(buy)
                                    rate = (sell_rate + buy_rate) / 2  # Or use sell_rate/buy_rate as in your original code

                                    data = {
                                        "country": "Indonesia",
                                        # 'date_of_page': current_date.strftime("%d-%b-%Y"),
                                        'unit': 'IDR',
                                        'Sell_Rate': sell_rate,
                                        'Buy_Rate': buy_rate,
                                        'value': rate,
                                        "date_of_page": exdate.strftime("%Y-%m-%d"),
                                        "website": url,
                                        "Source": "bank indonesia, bank sentral republik indonesia",
                                        "Status": "buy, sell"
                                    }
                                    results.append(data)
                                    print(f"Found data for {formatted_date}: Rate = {rate}")
                                    break  # Found USD data, break row loop

                        if results:  # If we found data, break the days loop
                            print(f"Data found for {formatted_date}, stopping search.")
                            break
                    else:
                        print(f"No data rows found for {formatted_date}")

                except Exception as table_error:
                    print(f"Table not found or empty for {formatted_date}: {table_error}")
                    # Check if there's a "no data" message
                    try:
                        no_data_msg = driver.find_element(By.XPATH, "//*[contains(text(), 'No data') or contains(text(), 'Tidak ada data')]")
                        print(f"Confirmed: No data available for {formatted_date}")
                    except:
                        pass  # No specific message found

            except Exception as e:
                print(f"Error processing {formatted_date}: {e}")
                continue

    except Exception as e:
        print(f"General error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()

    return results