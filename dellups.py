import csv
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# ==========================================================
# CONFIG
# ==========================================================

BASE_URL = "https://dellups.com/ups-selector/"

HEADLESS = True
TIMEOUT = 30000

OUTPUT_DIR = "dell_ups_test_output"
SCREENSHOT_DIR = os.path.join(OUTPUT_DIR, "screenshots")

RUN_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE = os.path.join(OUTPUT_DIR, f"dell_ups_results_{RUN_TIME}.csv")


# ==========================================================
# FALLBACK COUNTRY LIST
# ==========================================================

FALLBACK_COUNTRIES = [
    "Algeria",
    "Argentina",
    "Australia",
    "Austria",
    "Belgium",
    "Brazil",
    "Bulgaria",
    "Canada",
    "Chile",
    "China",
    "Colombia",
    "Costa Rica",
    "Croatia",
    "Czech Republic",
    "Denmark",
    "Egypt",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "India",
    "Indonesia",
    "Ireland",
    "Israel",
    "Italy",
    "Japan",
    "Korea",
    "Latvia",
    "Malaysia",
    "Mexico",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Peru",
    "Philippines",
    "Poland",
    "Portugal",
    "Romania",
    "Saudi Arabia",
    "Singapore",
    "Slovenia",
    "South Africa",
    "Spain",
    "Sweden",
    "Switzerland",
    "Thailand",
    "Turkey",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Vietnam",
]


# ==========================================================
# HELPERS
# ==========================================================

def create_output_folders():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)


def clean_filename(value):
    value = str(value).strip()
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value)
    return value[:100] if value else "unknown"


def wait_page_ready(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    page.wait_for_timeout(3000)


def save_screenshot(page, country_name):
    file_name = f"{clean_filename(country_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    file_path = os.path.join(SCREENSHOT_DIR, file_name)

    try:
        page.screenshot(path=file_path, full_page=True)
        return file_path
    except Exception:
        return ""


# ==========================================================
# COOKIE POPUP
# ==========================================================

def handle_cookie_popup(page):
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('Accept all')",
        "button:has-text('Allow all')",
        "button:has-text('I Agree')",
        "button:has-text('Agree')",
        "button:has-text('OK')",
        "button[id*='accept']",
        "button[class*='accept']",
    ]

    for selector in selectors:
        try:
            button = page.locator(selector)
            if button.count() > 0 and button.first.is_visible(timeout=1000):
                button.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                print("  ✓ Cookie popup handled")
                return True
        except Exception:
            continue

    return False


# ==========================================================
# COUNTRY DROPDOWN
# ==========================================================

def find_country_dropdown(page):
    selectors = [
        "select[name*='country' i]",
        "select[id*='country' i]",
        "select[class*='country' i]",
        "select",
    ]

    for selector in selectors:
        try:
            dropdowns = page.locator(selector)
            count = dropdowns.count()

            for i in range(count):
                dropdown = dropdowns.nth(i)

                try:
                    option_count = dropdown.locator("option").count()
                    if option_count > 1:
                        return dropdown
                except Exception:
                    continue

        except Exception:
            continue

    return None


def get_country_list(page):
    print("Reading country list...")

    dropdown = find_country_dropdown(page)
    countries = []

    if dropdown is not None:
        options = dropdown.locator("option")
        option_count = options.count()

        for i in range(option_count):
            try:
                option = options.nth(i)
                text = option.inner_text(timeout=2000).strip()
                value = option.get_attribute("value")

                if not text:
                    continue

                text_lower = text.lower().strip()

                skip_values = [
                    "select",
                    "choose",
                    "country",
                    "please select",
                    "--",
                ]

                if text_lower in skip_values:
                    continue

                if "select" in text_lower and len(text_lower) < 30:
                    continue

                countries.append({
                    "text": text,
                    "value": value if value else text,
                })

            except Exception:
                continue

    if not countries:
        print("Country dropdown not detected. Using fallback country list.")
        countries = [{"text": country, "value": country} for country in FALLBACK_COUNTRIES]

    unique_countries = []
    seen = set()

    for country in countries:
        key = country["text"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_countries.append(country)

    print(f"Countries found: {len(unique_countries)}")
    return unique_countries


def select_country(page, country):
    country_text = country["text"]
    country_value = country.get("value", country_text)

    dropdown = find_country_dropdown(page)

    if dropdown is not None:
        try:
            dropdown.select_option(value=country_value, timeout=10000)
            page.wait_for_timeout(2000)
            return True, f"Selected country by value: {country_value}"
        except Exception:
            pass

        try:
            dropdown.select_option(label=country_text, timeout=10000)
            page.wait_for_timeout(2000)
            return True, f"Selected country by label: {country_text}"
        except Exception:
            pass

    # Custom dropdown fallback
    custom_dropdown_selectors = [
        "[role='combobox']",
        "[class*='select']",
        "[class*='dropdown']",
        "button",
        "input",
    ]

    for selector in custom_dropdown_selectors:
        try:
            items = page.locator(selector)
            count = items.count()

            for i in range(min(count, 30)):
                item = items.nth(i)

                try:
                    if not item.is_visible(timeout=1000):
                        continue

                    item.click(timeout=3000)
                    page.wait_for_timeout(1000)

                    option = page.get_by_text(country_text, exact=True)

                    if option.count() > 0:
                        option.first.click(timeout=5000)
                        page.wait_for_timeout(2000)
                        return True, f"Selected country from custom dropdown: {country_text}"

                except Exception:
                    continue

        except Exception:
            continue

    return False, f"Country selection failed: {country_text}"


# ==========================================================
# CONTINUE BUTTON
# ==========================================================

def click_continue(page):
    try:
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(1000)
    except Exception:
        pass

    button_texts = [
        "Continue",
        "Submit",
        "Next",
        "Search",
        "Go",
        "Find",
        "Show Results",
    ]

    for text in button_texts:
        try:
            button = page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
            if button.count() > 0 and button.first.is_visible(timeout=1500):
                button.first.click(timeout=5000)
                page.wait_for_timeout(4000)
                return True, f"Clicked button: {text}"
        except Exception:
            continue

    fallback_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button[class*='primary']",
        "button[class*='submit']",
        "button[class*='continue']",
        "button",
        "a[class*='button']",
    ]

    for selector in fallback_selectors:
        try:
            items = page.locator(selector)
            count = items.count()

            for i in range(min(count, 25)):
                item = items.nth(i)

                try:
                    if not item.is_visible(timeout=1000):
                        continue

                    text = ""

                    try:
                        text = item.inner_text(timeout=1000).strip()
                    except Exception:
                        pass

                    text_lower = text.lower()

                    skip_words = [
                        "accept",
                        "cookie",
                        "privacy",
                        "terms",
                        "login",
                        "register",
                    ]

                    if any(skip in text_lower for skip in skip_words):
                        continue

                    item.click(timeout=5000)
                    page.wait_for_timeout(4000)
                    return True, f"Clicked fallback button: {text}"

                except Exception:
                    continue

        except Exception:
            continue

    return False, "Continue button not found"


# ==========================================================
# VALIDATION
# ==========================================================

def check_results_page_opened(page, before_url):
    current_url = page.url

    if current_url != before_url:
        return True, f"URL changed to: {current_url}"

    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        body_text = ""

    result_words = [
        "results",
        "recommended",
        "products",
        "product",
        "ups",
        "apc",
        "battery backup",
    ]

    if any(word in body_text for word in result_words):
        return True, "Result-related text detected on page"

    return False, "Result page not clearly opened"


def detect_no_results(page):
    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        return False, ""

    no_result_texts = [
        "0 results",
        "no results",
        "nothing found",
        "no product",
        "no products",
        "no matching",
        "not found",
        "no ups",
    ]

    for text in no_result_texts:
        if text in body_text:
            return True, text

    return False, ""


def detect_products(page):
    page.wait_for_timeout(3000)

    try:
        page.mouse.wheel(0, 1000)
        page.wait_for_timeout(1000)
    except Exception:
        pass

    no_results, no_result_text = detect_no_results(page)

    if no_results:
        return False, 0, f"No-result text detected: {no_result_text}"

    product_selectors = [
        "[class*='product']",
        "[class*='Product']",
        "[class*='result']",
        "[class*='Result']",
        "[class*='card']",
        "[class*='Card']",
        "a[href*='ups']",
        "a[href*='apc']",
        "a[href*='product']",
        "a[href*='battery']",
    ]

    product_hints = [
        "apc",
        "ups",
        "va",
        "watt",
        "battery",
        "backup",
        "back-ups",
        "easy ups",
        "smart ups",
        "bx",
        "br",
        "be",
    ]

    ignore_hints = [
        "cookie",
        "privacy",
        "terms",
        "contact",
        "support",
        "login",
        "register",
        "facebook",
        "linkedin",
        "youtube",
        "twitter",
        "instagram",
        "download",
    ]

    found_items = []
    seen = set()

    for selector in product_selectors:
        try:
            items = page.locator(selector)
            count = items.count()

            for i in range(min(count, 50)):
                item = items.nth(i)

                try:
                    if not item.is_visible(timeout=800):
                        continue

                    text = ""
                    href = ""

                    try:
                        text = item.inner_text(timeout=1000).strip()
                    except Exception:
                        pass

                    try:
                        href = item.get_attribute("href") or ""
                    except Exception:
                        pass

                    combined = f"{text} {href}".lower().strip()

                    if not combined:
                        continue

                    if any(ignore in combined for ignore in ignore_hints):
                        continue

                    if not any(hint in combined for hint in product_hints):
                        continue

                    key = combined[:250]

                    if key not in seen:
                        seen.add(key)
                        found_items.append(combined)

                except Exception:
                    continue

        except Exception:
            continue

    if found_items:
        return True, len(found_items), f"Visible product indicators detected: {len(found_items)}"

    return False, 0, "No visible product cards/items detected"


# ==========================================================
# TEST SINGLE COUNTRY
# ==========================================================

def test_country(browser, country, index, total):
    country_name = country["text"]

    print("\n==================================================")
    print(f"[{index}/{total}] Testing country: {country_name}")
    print("==================================================")

    context = browser.new_context(
        viewport={"width": 1440, "height": 1200},
        ignore_https_errors=True,
    )

    page = context.new_page()
    page.set_default_timeout(TIMEOUT)

    status = "FAIL"
    results_page_opened = "NO"
    products_detected = 0
    reason = ""
    continue_clicked = "NO"
    screenshot = ""
    final_url = ""

    try:
        print(f"  Opening URL: {BASE_URL}")

        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        wait_page_ready(page)
        handle_cookie_popup(page)

        before_url = page.url

        selected, selected_reason = select_country(page, country)

        if not selected:
            reason = selected_reason
            screenshot = save_screenshot(page, country_name)
            final_url = page.url

            print(f"  FAILED: {reason}")

            return [
                country_name,
                results_page_opened,
                status,
                reason,
                continue_clicked,
                products_detected,
                final_url,
                screenshot,
            ]

        print(f"  ✓ {selected_reason}")

        clicked, click_reason = click_continue(page)

        if clicked:
            continue_clicked = "YES"
            print(f"  ✓ {click_reason}")
        else:
            continue_clicked = "NO"
            print(f"  ⚠ {click_reason}")

        wait_page_ready(page)

        opened, opened_reason = check_results_page_opened(page, before_url)

        if opened:
            results_page_opened = "YES"
            print(f"  ✓ Results page opened: {opened_reason}")
        else:
            results_page_opened = "NO"
            print(f"  ⚠ Results page not clear: {opened_reason}")

        products_found, products_detected, product_reason = detect_products(page)

        final_url = page.url
        screenshot = save_screenshot(page, country_name)

        if opened and products_found:
            status = "PASS"
            reason = product_reason
        elif not opened:
            status = "FAIL"
            reason = opened_reason
        else:
            status = "FAIL"
            reason = product_reason

        print(f"  Status: {status}")
        print(f"  Products Detected: {products_detected}")
        print(f"  Reason: {reason}")
        print(f"  Final URL: {final_url}")
        print(f"  Screenshot: {screenshot}")

    except Exception as e:
        status = "FAIL"
        reason = f"Exception: {str(e)}"
        final_url = page.url

        try:
            screenshot = save_screenshot(page, country_name)
        except Exception:
            screenshot = ""

        print(f"  Exception: {str(e)}")

    finally:
        context.close()

    return [
        country_name,
        results_page_opened,
        status,
        reason,
        continue_clicked,
        products_detected,
        final_url,
        screenshot,
    ]


# ==========================================================
# MAIN
# ==========================================================

def main():
    create_output_folders()

    print("==================================================")
    print("Dell UPS Selector - All Countries Test")
    print("==================================================")
    print(f"URL: {BASE_URL}")
    print(f"CSV Report: {CSV_FILE}")
    print(f"Screenshots Folder: {SCREENSHOT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        setup_context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            ignore_https_errors=True,
        )

        setup_page = setup_context.new_page()
        setup_page.set_default_timeout(TIMEOUT)

        try:
            print("\nOpening page to read country list...")

            setup_page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            wait_page_ready(setup_page)
            handle_cookie_popup(setup_page)

            countries = get_country_list(setup_page)

        finally:
            setup_context.close()

        if not countries:
            browser.close()
            raise Exception("No countries found")

        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)

            writer.writerow([
                "Country",
                "Results Page Opened",
                "Status",
                "Reason",
                "Continue Clicked",
                "Products Detected",
                "Final URL",
                "Screenshot",
            ])

            total = len(countries)

            for index, country in enumerate(countries, start=1):
                row = test_country(browser, country, index, total)
                writer.writerow(row)
                csv_file.flush()

        browser.close()

    print("\n==================================================")
    print("TEST COMPLETED")
    print(f"CSV Report saved: {CSV_FILE}")
    print(f"Screenshots saved: {SCREENSHOT_DIR}")
    print("==================================================")


if __name__ == "__main__":
    main()
