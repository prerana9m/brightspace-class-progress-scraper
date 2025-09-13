# Brightspace Class Progress Scraper — Detailed Guide

This document explains **what the script does**, **what you need to use or adapt it**, and **how to customize it** for your own Brightspace/D2L tenant. It’s written for developers or power users who want to **adopt** and **modify** the code; it does *not* assume you’ll run anything on GitHub.

> ⚠️ **Ethics & Authorization**  
> Use this only on systems you’re **authorized** to access. If your data involves students, comply with your institution’s rules (FERPA/GDPR or local equivalents). Do not publish credentials, Duo info, or datasets with PII.

---

## 1) What this script does (high level)

- **Logs into Brightspace/D2L** via the standard login flow for your tenant (configured by `BASE_URL`).  
- **Navigates to the “Class Progress” list** for a specific course (`ORG_UNIT`).  
- **Iterates pages** of the class progress view.  
- **Finds “Video” rows** on each page (links with text containing “Video”).  
- **Extracts visit/engagement info** and accumulates it into:  
  - A **per-page Excel** file: `video_data_page_{page_num}.xlsx`  
  - A **master Excel** file: `video_data_master.xlsx` (all pages combined)  
- **Saves screenshots** on notable failures for diagnosis (e.g., Duo issues, timeouts).

> The script uses `selenium`, `pandas`, and `python-dotenv`. Chrome is expected to be installed locally. Selenium 4’s driver manager can auto-manage the ChromeDriver in most environments.

---

## 2) Architecture & data flow

```
+-------------------+        +---------------------+         +-------------------------+
| .env (secrets)    |  -->   | Selenium WebDriver  |  -->    | Brightspace (Class Prog)|
| USERNAME, PASSWORD|        | (Chrome)            |         |  - Login (SSO/SAML/Duo) |
| BASE_URL, ORG_UNIT|        |                     |         |  - Class Progress list  |
+-------------------+        +----------+----------+         +-----------+-------------+
                                         |                                |
                                         v                                v
                               +--------------------+            +------------------------+
                               | HTML scraping      |            | “Video” row extraction |
                               | (find elements)    |            | per page               |
                               +----------+---------+            +-----------+------------+
                                          \                               /
                                           \                             /
                                            v                           v
                                       +-------------------------------+
                                       | pandas DataFrames             |
                                       | - per-page dataframe          |
                                       | - master dataframe            |
                                       +-------------------------------+
                                           |                      |
                                           v                      v
                               video_data_page_{n}.xlsx   video_data_master.xlsx
```

**Key helpers present in the code:**
- `take_screenshot(name)` — snapshot current screen on error cases.
- `dump_page(name)` — (debug) prints URL and a truncated HTML snippet.
- `navigate_to_page_by_typing(target_page_num, driver, wait, CLASS_LIST)` — goes directly to a given page in the Class Progress list by typing into the page number host input.

> The script uses robust waits via `WebDriverWait` + `expected_conditions` to reduce flakiness in dynamic pages.

---

## 3) Requirements

### Software
- **Python 3.10+** (3.11 recommended)
- **Google Chrome** desktop browser installed
- **Pip-installed libraries** (see `requirements.txt` for exact versions):
  - `selenium`
  - `python-dotenv`
  - `pandas`

> If your environment lacks admin rights, you can still install Python under your user account and run Chrome portable. Selenium 4’s **Selenium Manager** usually finds the proper driver automatically.

### Accounts & permissions
- A **Brightspace/D2L account** with access to the target course’s **Class Progress**.
- Authorization to view and export the data you scrape.

### Network/SSO
- The script expects normal SSO/SAML login. If **Duo** or other 2FA is used, you will likely need to **approve a push challenge** on your device.
- The included code attempts to detect a **Duo iframe** and read a short code if present; **do not rely on this as a bypass**. It’s for visibility/diagnostics only and may break as Duo or your tenant updates their UI.

---

## 4) Configuration

The script reads credentials from environment variables via `python-dotenv`:

Create a local (untracked) `.env` file next to your script:

```ini
USERNAME=your.username@school.edu
PASSWORD=yourStrongPassword
```

**Tenant & course** (in script):
```python
BASE_URL = "https://purdue.brightspace.com"
ORG_UNIT = "1209238"
```

To make adoption easier, you can switch to environment variables with safe defaults:
```python
import os
BASE_URL = os.getenv("BASE_URL", "https://purdue.brightspace.com").strip()
ORG_UNIT = os.getenv("ORG_UNIT", "1209238").strip()
```

Then expand `.env`:
```ini
USERNAME=your.username@school.edu
PASSWORD=yourStrongPassword
BASE_URL=https://yourtenant.brightspace.com
ORG_UNIT=123456
```

---

## 5) How it works (step-by-step)

1. **Load env**: `load_dotenv()` then read `USERNAME`, `PASSWORD` (`os.getenv(...)`).  
2. **Spin up Chrome**: `webdriver.Chrome()` with waits. You can add headless mode later if desired.  
3. **Go to login**: `driver.get(f"{BASE_URL}/d2l/lp/auth/saml/initiate-login?")` (URL patterns may vary by tenant).  
4. **Authenticate**: Fill username/password if forms are visible; otherwise follow SSO redirects. Approve **Duo** if prompted (manual).  
5. **Open Class Progress** for the course:  
   `CLASS_LIST = f"{BASE_URL}/d2l/le/userprogress/{ORG_UNIT}/classprogress/List"`  
6. **Wait for the page title**: checks `h1.d2l-page-title` contains “Class Progress”.  
7. **Paginate**: Uses the `d2l-input-number[label='Page Number']` control by typing the target page number. Everytime brightspace returns to class progress page to start data collection for next student, it reaches page 1, therefore it is 
necessary to write the current page number after each student. A different LMS may have different page loading dynamics.  
8. **Extract Student id and “Video” rows**: For each student crawler clicks 1) All modules 2) All chapters, to finally locates anchors where the visible text contains “Video”; scrapes fields (e.g., title, visit counts/duration; exact selectors depend on your tenant).  
9. **Write output**:  
   - Per-page Excel: `video_data_page_{page_num}.xlsx`  
   - Master Excel: `video_data_master.xlsx` (append/concat).
10. **Error handling**: On `TimeoutException` or element issues, takes a screenshot (e.g., `ERROR_duo_code_missing.png`, `ERROR_navigate_to_page_{n}.png`) and logs a message.

> **Selectors matter.** Brightspace tenants differ slightly: labels/text may vary, and custom themes can alter CSS. Expect to tweak XPaths or CSS selectors for your instance.

---

## 6) Adapting to *your* Brightspace tenant

1. **Change the tenant URL**: set `BASE_URL="https://<yourdomain>.brightspace.com"`.  
2. **Find the course ORG_UNIT**: open your course in a browser → copy the numeric id in the URL for Class Progress.  
3. **Confirm the “Class Progress” page title**: your tenant may localize the string; change the expected text in the wait condition if needed.  
4. **Check the “Video” label**: if your analytics page uses different link text (e.g., “Media”, “Kaltura”), update the locator:
   ```python
   driver.find_elements(By.XPATH, "//a[contains(normalize-space(.), 'Video')]")
   ```
   Replace `'Video'` with the term shown in your UI.

5. **Adjust table/field selectors**: Inspect element (F12) and refine XPaths to capture the fields you need.

---

## 7) Customization ideas

- **Headless mode**:  
  ```python
  from selenium.webdriver.chrome.options import Options
  opts = Options()
  opts.add_argument("--headless=new")
  driver = webdriver.Chrome(options=opts)
  ```
- **CLI flags** (argparse) to pass `--base-url`, `--org-unit`, `--headless`.  
- **Rate limiting**: add `time.sleep(0.3)` between page navigations to avoid throttling.  
- **Resumable runs**: remember the last successful page in a small state file.  
- **Structured output**: write CSV/Parquet in addition to Excel.  
- **Anonymization**: hash student identifiers before export if you’re sharing data.

---

## 8) Output schema (example)

The exact columns depend on your tenant’s markup. Typical fields you might collect:

| Column                | Description                                    |
|-----------------------|------------------------------------------------|
| `student_name`        | Student’s display name                          |
| `student_id`          | Internal id or username                         |
| `item_title`          | “Video” resource title                          |
| `visits`              | Number of visits                                |
| `total_time`          | Total time spent                                |
| `page_num`            | Class Progress page number                       |
| `scraped_at`          | Timestamp of extraction                          |

> Inspect your generated Excel files to confirm and rename columns for clarity.

---

## 9) Troubleshooting

- **`TimeoutException` waiting for page title**  
  - The page title text is different in your tenant. Update the expected string.
  - Network/SSO took longer than your timeout; increase wait time.

- **`NoSuchElementException` on “Video” selector**  
  - The link text isn’t identical (e.g., “Media”). Change the XPath to match your UI.
  - The element is inside a different frame; ensure you’ve switched to it.

- **Duo/2FA issues**  
  - The script cannot (and should not) bypass 2FA. Approve each prompt. Disable any brittle code that tries to read short-lived codes if it causes failures.

- **Excel not created**  
  - Confirm write permissions in the working directory.
  - Ensure your DataFrame is not empty (check logs).

---

## 10) Privacy & security checklist

- **Never** hardcode real credentials. Use `.env` (untracked).  
- **Do not** commit output files with PII.  
- **Document** lawful use in your README.  
- **Rotate** passwords if you tested with real accounts.  
- **Avoid** scraping Duo/2FA codes. Treat that code path as diagnostic-only or remove it.

---

## 11) Minimal “getting started” (local use)

```bash
# 1) Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2) Install dependencies
pip install selenium pandas python-dotenv

# 3) Create a .env file (same folder as the script)
# USERNAME=...
# PASSWORD=...
# BASE_URL=https://yourtenant.brightspace.com
# ORG_UNIT=123456

# 4) Run
python src/crawler.py
```

---

## 12) Roadmap / nice-to-haves

- Replace hardcoded `BASE_URL`/`ORG_UNIT` with CLI/env first-class inputs.
- Add **unit tests** for HTML parsing (using saved test fixtures).
- Add **retry** logic on transient nav failures.
- Produce **CSV + Parquet** outputs for analytics pipelines.
- Add a **config file** (YAML) to define selectors per tenant (pluggable adapter).

---

### Final tip
When you adapt this to another tenant or layout, change **one thing at a time**: confirm login, then Class Progress title, then Video link selection, then table fields. Take screenshots on every change; it will save you hours.
