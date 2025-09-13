import os
import time
import re
import pandas as pd
from collections import Counter
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException,
)
from dotenv import load_dotenv


def dump_page(name):
    print(f"\n\n==== {name} ====")
    print("URL:", driver.current_url)
    print(driver.page_source[:15000], "\n…\n")
    print(f"==== end {name} ====\n\n")


def take_screenshot(name):
    filename = f"{name.replace(' ', '_')}.png"
    driver.save_screenshot(filename)
    print(f"📸 saved screenshot: {filename}")


def navigate_to_page_by_typing(target_page_num, driver, wait, CLASS_LIST):
    print(f"    Navigating to target page {target_page_num} by typing…")
    try:
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "h1.d2l-page-title"), "Class Progress"
        ))
    except TimeoutException:
        print(f"⚠️ Could not confirm Class Progress title before navigation to page {target_page_num}. Reloading CLASS_LIST.")
        take_screenshot(f"ERROR_navigate_to_page_{target_page_num}")
        driver.get(CLASS_LIST)
        wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, "h1.d2l-page-title"), "Class Progress"
        ))
    try:
        host = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "d2l-input-number[label='Page Number']"
        )))
        driver.execute_script("arguments[0].scrollIntoView(true);", host)
        host.click()
        host.send_keys(Keys.CONTROL, "a")
        host.send_keys(str(target_page_num), Keys.ENTER)
        wait.until(lambda d: host.get_attribute("value") == str(target_page_num))
        time.sleep(15)
    except Exception as e:
        print(f"⚠️ Failed to navigate to page {target_page_num}: {e}")
        take_screenshot(f"ERROR_navigate_input_{target_page_num}")

# ─── Config & creds ────────────────────────────────────────────────────────────
BASE_URL = "https://purdue.brightspace.com"
ORG_UNIT = "1209238"
CLASS_LIST = (
    f"{BASE_URL}/d2l/le/userprogress/{ORG_UNIT}/classprogress/List"
    "?searchString=&sortDescending=0&sortField=SortLastName"
)
load_dotenv(override=True)
USERNAME = os.getenv("USERNAME", "").strip()
PASSWORD = os.getenv("PASSWORD", "").strip()

# ─── Selenium setup ───────────────────────────────────────────────────────────
options = webdriver.ChromeOptions()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

# ─── 1) LOGIN ─────────────────────────────────────────────────────────────────
driver.get(
    "https://purdue.brightspace.com/d2l/lp/auth/saml/initiate-login?"
    "entityId=https://idp.purdue.edu/idp/shibboleth"
)
wait.until(EC.presence_of_element_located((By.NAME, "j_username"))).send_keys(USERNAME)
driver.find_element(By.NAME, "j_password").send_keys(PASSWORD)
login_btn = wait.until(EC.element_to_be_clickable((By.NAME, "_eventId_proceed")))
driver.execute_script("arguments[0].click();", login_btn)

# ─── 2) DUO 2FA ────────────────────────────────────────────────────────────────
try:
    wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe")))
except TimeoutException:
    print("⚠️ Duo iframe not found, continuing...")
try:
    codes = wait.until(EC.presence_of_all_elements_located(
        (By.XPATH, "//*[string-length(normalize-space(text()))=3]")
    ))
    duo_code = next((el.text for el in codes if re.fullmatch(r"\d{3}", el.text.strip())), None)
    if not duo_code:
        raise RuntimeError("Duo code not found")
    print("Duo code →", duo_code)
except Exception as e:
    print(f"⚠️ Could not retrieve Duo code: {e}")
    take_screenshot("ERROR_duo_code_missing")
    driver.quit()
    raise

driver.switch_to.default_content()
wait.until(EC.url_contains("/d2l/home"))

# ─── 3) SCRAPE & CLICK MODULE BUTTONS ───────────────────────────────────────────
video_records = []
unique_students = set()

driver.get(CLASS_LIST)
print("\nAttempting to set items per page to 50...")
try:
    select_locator = (By.CSS_SELECTOR, ".d2l-numericpager-pagesize-container select.d2l-select")
    select_elem = wait.until(EC.presence_of_element_located(select_locator))
    select = Select(select_elem)
    if "50" in [opt.get_attribute("value") for opt in select.options]:
        if select.first_selected_option.get_attribute("value") != "50":
            select.select_by_value("50")
            time.sleep(2)
except Exception as e:
    print(f"⚠️ Error setting items per page: {e}")
    take_screenshot("ERROR_set_page_size")

# Determine total pages
total_pages = 1
try:
    page_count_elem = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "d2l-numericpager-pagecount")))
    text = page_count_elem.text.strip()
    print(f"Raw page count text: '{text}'")
    total_pages = int(text)
    print(f"Parsed total pages: {total_pages}")
except Exception as e:
    print(f"⚠️ Failed to determine total pages: {e}")
    take_screenshot("ERROR_get_total_pages")

# Main scraping loop over pages 2..N
for page_num in range(1, total_pages + 1):
    page_records = []
    navigate_to_page_by_typing(page_num, driver, wait, CLASS_LIST)
    try:
        rows = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "d2l-grid-row")))
        print(f"Found {len(rows)} students on page {page_num}")
    except Exception as e:
        print(f"⚠️ Failed to load rows on page {page_num}: {e}")
        take_screenshot(f"ERROR_load_rows_page_{page_num}")
        continue

    for i in range(len(rows)):
        try:
            rows = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "d2l-grid-row")))
            row = rows[i]
        except Exception as e:
            print(f"⚠️ Could not access row {i} on page {page_num}: {e}")
            take_screenshot(f"ERROR_row_access_page{page_num}_idx{i}")
            continue

        try:
            identifier = row.find_element(By.XPATH,
                ".//div[@class='d2l-textblock d2l-textblock-secondary'][1]"
            ).text
            print(f"\n→ Student ID: {identifier}")
            unique_students.add(identifier)
            row.find_element(By.CSS_SELECTOR, "td svg rect").click()
            wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "h1.d2l-page-title"), "Content Progress"))
        except Exception as e:
            print(f"⚠️ Failed to enter student {i} on page {page_num}: {e}")
            take_screenshot(f"ERROR_enter_student_page{page_num}_idx{i}")
            continue

        try:
            # Module clicks
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'd2l-button-subtle[text="0 Topics, 3 Modules"]'))).click()
            #take_screenshot(f"{identifier}_first")
            for title in ["0 Topics, 5 Modules", "0 Topics, 6 Modules"]:
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'd2l-button-subtle[text="{title}"]'))).click()
                #take_screenshot(f"{identifier}_{title.replace(' ', '_')}")
            elems = driver.find_elements(By.CSS_SELECTOR, 'd2l-button-subtle[text="0 Topics, 5 Modules"]')
            if len(elems) >= 2:
                btn = elems[1]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                try:
                    btn.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", btn)
                #take_screenshot(f"{identifier}_second_0_Topics_5_Modules")
            time.sleep(2)
            chapter_buttons = [
                "14 Topics, 1 Modules", "17 Topics, 1 Modules", "16 Topics, 1 Modules",
                "15 Topics, 1 Modules", "15 Topics, 0 Modules", "14 Topics, 1 Modules",
                "18 Topics, 1 Modules", "17 Topics, 1 Modules", "18 Topics, 1 Modules",
                "18 Topics, 1 Modules", "18 Topics, 1 Modules", "15 Topics, 1 Modules",
                "19 Topics, 1 Modules"
            ]
            counts = Counter(chapter_buttons)
            for key, total in counts.items():
                for occ in range(1, total + 1):
                    elems = driver.find_elements(By.CSS_SELECTOR, f'd2l-button-subtle[text="{key}"]')
                    if len(elems) < occ:
                        print(f"⚠️ Missing occurrence #{occ} of '{key}' for {identifier}")
                        #take_screenshot(f"ERROR_missing_{key.replace(' ', '_')}_{identifier}")
                        continue
                    btn = elems[occ-1]
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    try:
                        btn.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", btn)
                    #take_screenshot(f"{identifier}_{key.replace(' ', '_')}_{occ}")
                    time.sleep(1)
        except Exception as e:
            print(f"⚠️ Error clicking modules/chapters for {identifier}: {e}")
            take_screenshot(f"ERROR_module_clicks_{identifier}")

        try:
            time.sleep(2)
            for vid in driver.find_elements(By.XPATH, "//a[contains(normalize-space(.), 'Video')]"):
                title = vid.text.strip()
                try:
                    container = vid.find_element(By.XPATH, "./ancestor::li[1]")
                except NoSuchElementException:
                    container = vid.find_element(By.XPATH, "./..")
                lines = container.text.splitlines()
                visits_idx = next((j for j, ln in enumerate(lines) if "visits" in ln), None)
                if visits_idx is not None:
                    visits = int(re.search(r"(\d+)\s+visits", lines[visits_idx]).group(1))
                    duration = lines[visits_idx+1].strip() if visits_idx+1 < len(lines) else ""
                else:
                    visits = 0
                    duration = ""
                record = {"student": identifier, "video_title": title, "visits": visits, "duration": duration}
                video_records.append(record)
                page_records.append(record)
        except Exception as e:
            print(f"⚠️ Error scraping videos for {identifier}: {e}")
            take_screenshot(f"ERROR_scrape_videos_{identifier}")

        # Return to class list
        try:
            driver.back()
            wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "h1.d2l-page-title"), "Class Progress"))
        except Exception as e:
            print(f"⚠️ Failed to return to class list after {identifier}: {e}")
            take_screenshot(f"ERROR_return_class_{identifier}")
        navigate_to_page_by_typing(page_num, driver, wait, CLASS_LIST)

    try:
        df_page = pd.DataFrame(page_records)
        page_file = f"video_data_page_{page_num}.xlsx"
        print(f"Saving page {page_num} data to: {os.path.abspath(page_file)}")
        with pd.ExcelWriter(page_file) as writer:
            df_page.to_excel(writer, index=False, sheet_name="VideoData")
            pd.DataFrame({"total_students": [len(page_records)]}) \
              .to_excel(writer, index=False, sheet_name="Summary")
    except Exception as e:
        print(f"⚠️ Failed saving page {page_num} file: {e}")
        take_screenshot(f"ERROR_save_page_{page_num}")

# ─── WRITE MASTER EXCEL ─────────────────────────────────────────────────────────
try:
    df_master = pd.DataFrame(video_records)
    master_file = "video_data_master.xlsx"
    print(f"Saving master data to: {os.path.abspath(master_file)}")
    with pd.ExcelWriter(master_file) as writer:
        df_master.to_excel(writer, index=False, sheet_name="VideoData")
        pd.DataFrame({"total_students": [len(unique_students)]}) \
          .to_excel(writer, index=False, sheet_name="Summary")
except Exception as e:
    print(f"⚠️ Failed saving master file: {e}")
    take_screenshot("ERROR_save_master")

driver.quit()
