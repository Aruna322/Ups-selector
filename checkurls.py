import csv
import time

# Playwright helps Python open a real browser like Edge/Chrome
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# input file name
# this file should contain one URL per line
INPUT_FILE = "urls-bothupsrbc.txt"

# output CSV file name
# final report will be saved here
OUTPUT_FILE = "report.csv"

# maximum wait time for one website to open = 30 seconds
PAGE_TIMEOUT = 30000

# wait 2 seconds before opening next URL
# this avoids hitting too many URLs too fast
DELAY_BETWEEN_URLS = 2

# this empty list will store all results
results = []

# open the input file and read all URLs
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    # remove blank lines and extra spaces
    urls = [line.strip() for line in f if line.strip()]

# count total URLs
total = len(urls)

# show total count on screen
print(f"Total URLs found: {total}")
print("-" * 140)

# start Playwright
with sync_playwright() as p:

    # open Microsoft Edge in background
    # headless=True means browser will NOT open on screen
    # so it will not disturb your other work
    browser = p.chromium.launch(
        headless=False,
        channel="msedge"
    )

    # create one clean browser session
    # ignore_https_errors=True helps avoid SSL/certificate issues
    context = browser.new_context(ignore_https_errors=True)

    # check URLs one by one
    for index, url in enumerate(urls, start=1):

        # open a fresh new tab for each URL
        page = context.new_page()

        # set maximum page load wait time
        page.set_default_navigation_timeout(PAGE_TIMEOUT)

        # keep empty values ready
        status_code = ""
        final_url = ""
        result = ""
        error_msg = ""

        try:
            # open the URL
            # wait until basic page content is loaded
            response = page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

            # wait a little extra so redirects or dynamic content can finish loading
            page.wait_for_timeout(3000)

            # get the final page URL after redirect
            final_url = page.url

            # get status code like 200, 403, 404
            # sometimes response can be empty, so check safely
            status_code = response.status if response else ""

            # decide final result
            if status_code == 200:
                result = "PASS"          # page opened successfully
            elif status_code == 403:
                result = "FORBIDDEN"     # page opened but access denied
            elif status_code in [301, 302, 307, 308]:
                result = "REDIRECT"      # URL redirected to another page
            elif status_code:
                result = "FAIL"          # page opened but not successful
            else:
                result = "CHECK"         # no clear response, manual review needed

            # show current progress on screen
            print(f"[{index}/{total}] {result} | Status: {status_code} | URL: {url}")

            # save result in memory
            results.append([index, url, status_code, final_url, result, error_msg])

        except PlaywrightTimeoutError as e:
            # if website takes too long to open
            error_msg = f"Timeout: {e}"
            print(f"[{index}/{total}] ERROR | URL: {url} | Reason: {error_msg}")
            results.append([index, url, "", "", "ERROR", error_msg])

        except Exception as e:
            # if any other problem happens
            # like browser/network/security issue
            error_msg = str(e)
            print(f"[{index}/{total}] ERROR | URL: {url} | Reason: {error_msg}")
            results.append([index, url, "", "", "ERROR", error_msg])

        finally:
            # close current tab after checking one URL
            page.close()

        # small wait before next URL
        time.sleep(DELAY_BETWEEN_URLS)

    # close browser after all URLs are done
    browser.close()

# save all results into CSV file
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)

    # first row = column names
    writer.writerow(["S.No", "Original URL", "Status Code", "Final URL", "Result", "Error"])

    # write all results
    writer.writerows(results)

# final message
print("-" * 140)
print(f"Report saved as: {OUTPUT_FILE}")
