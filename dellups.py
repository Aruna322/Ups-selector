import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ==========================================================
# CONFIG
# ==========================================================

BASE_URL = "https://dellups.com/ups-selector/"

HEADLESS = True
TIMEOUT = 30000

OUTPUT_DIR = "dell_ups_test_output"
SCREENSHOT_DIR = os.path.join(OUTPUT_DIR, "screenshots")

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE = os.path.join(OUTPUT_DIR, f"dell_ups_results_{TIMESTAMP}.csv")


# ==========================================================
# BASIC HELPERS
# ==========================================================

def create_dirs():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)


def safe_filename(text):
    text = str(text).strip()
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)
    return text[:100] if text else "unknown"


def save_screenshot(page, country):
    filename = f"{safe_filename(country)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)

    try:
        page.screenshot(path=path, full_page=True)
        return path
    except Exception:
        return ""


def wait_page_ready(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    page.wait_for_timeout(2000)


# ==========================================================
# COOKIE HANDLING
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
            locator = page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible(timeout=1000):
                locator.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                print("  ✓ Cookie popup handled")
                return True
        except Exception:
            continue

    return False


# ==========================================================
# COUNTRY DROPDOWN
# ==========================================================

def find_country_select(page):
    """
    Finds the real country dropdown.
    Priority is normal <select> element.
    """

    possible_selectors = [
        "select",
        "select[name*='country' i]",
        "select[id*='country' i]",
        "select[class*='country' i]",
    ]

    for selector in possible_selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()

            for i in range(count):
                item = loc.nth(i)

                try:
                    if item.is_visible(timeout=1000):
                        options_count = item.locator("option").count()
                        if options_count > 1:
                            return item
                except Exception:
                    continue

        except Exception:
            continue

    return None


def get_all_countries(page):
    """
    Reads all countries from dropdown.
    """

    print("Reading countries from dropdown...")

    select = find_country_select(page)

    if select is None:
        raise Exception("Country dropdown not found")

    options = select.locator("option")
    option_count = options.count()

    countries = []

    for i in range(option_count):
        try:
            option = options.nth(i)

            text = option.inner_text(timeout=2000).strip()
            value = option.get_attribute("value")

            if not text:
                continue

            skip_words = [
                "select",
                "choose",
                "country",
                "please",
                "--",
            ]

            if text.lower() in skip_words:
                continue

            if "select" in text.lower() and len(text) < 20:
                continue

            countries.append({
                "text": text,
                "value": value if value else text
            })

        except Exception:
            continue

    unique = []
    seen = set()

    for country in countries:
        key = country["text"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(country)

    print(f"Countries found: {len(unique)}")
    return unique


def select_country(page, country):
    """
    Selects a country from dropdown using value first, then label fallback.
    """

    select = find_country_select(page)

    if select is None:
        return False, "Country dropdown not found"

    try:
        if country.get("value"):
            select.select_option(value=country["value"], timeout=10000)
            page.wait_for_timeout(2000)
            return True, f"Selected by value: {country['value']}"
    except Exception:
        pass

    try:
        select.select_option(label=country["text"], timeout=10000)
        page.wait_for_timeout(2000)
        return True, f"Selected by label: {country['text']}"
    except Exception as e:
        return False, f"Country selection failed: {str(e)}"


# ==========================================================
# CONTINUE BUTTON
# ==========================================================

def click_continue_button(page):
    """
    Clicks Continue/Submit button after country selection.
    """

    page.wait_for_timeout(1000)

    try:
        page.mouse.wheel(0, 800)
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
            btn = page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
            if btn.count() > 0 and btn.first.is_visible(timeout=1500):
                btn.first.click(timeout=5000)
                page.wait_for_timeout(4000)
                return True, f"Clicked button by text: {text}"
        except Exception:
            continue

    selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button.primary",
        "button[class*='primary']",
        "button[class*='submit']",
        "button[class*='continue']",
        "button",
        "a[class*='button']",
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()

            for i in range(min(count, 20)):
                btn = loc.nth(i)

                try:
                    if not btn.is_visible(timeout=1000):
                        continue

                    text = ""
                    try:
                        text = btn.inner_text(timeout=1000).strip()
                    except Exception:
                        pass

                    combined = text.lower()

                    bad_words = [
                        "accept",
                        "cookie",
                        "privacy",
                        "terms",
                        "login",
                        "register",
                    ]

                    if any(bad in combined for bad in bad_words):
                        continue

                    btn.click(timeout=5000)
                    page.wait_for_timeout(4000)
                    return True, f"Clicked fallback button: {text}"

                except Exception:
                    continue

        except Exception:
            continue

    return False, "Continue/Submit button not found"


# ==========================================================
# RESULT PAGE VALIDATION
# ==========================================================

def check_results_page_opened(page, before_url):
    current_url = page.url

    if current_url != before_url:
        return True, f"URL changed from home page to: {current_url}"

    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        body_text = ""

    result_indicators = [
        "results",
        "recommended",
        "products",
        "product",
        "ups",
        "apc",
        "battery backup",
    ]

    if any(word in body_text for word in result_indicators):
        return True, "Result-related content detected on page"

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
    """
    Detects real visible product cards/links.
    Avoids relying only on page keywords.
    """

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

    found = []
    seen = set()

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

    for selector in product_selectors:
        try:
            loc = page.locator(selector)
            count = loc.count()

            for i in range(min(count, 50)):
                item = loc.nth(i)

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

                    if any(bad in combined for bad in ignore_hints):
                        continue

                    if not any(hint in combined for hint in product_hints):
                        continue

                    key = combined[:250]

                    if key not in seen:
                        seen.add(key)
                        found.append(combined)

                except Exception:
                    continue

        except Exception:
            continue

    if found:
        return True, len(found), f"Visible product indicators detected: {len(found)}"

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
        ignore_https_errors=True
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

            print(f"  ✗ {reason}")

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

        clicked, click_reason = click_continue_button(page)

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

        print(f"  ✗ Exception: {str(e)}")

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
    create_dirs()

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
                "--disable-dev-shm-usage"
            ]
        )

        setup_context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            ignore_https_errors=True
        )

        setup_page = setup_context.new_page()
        setup_page.set_default_timeout(TIMEOUT)

        try:
            print("\nOpening page to read country list...")
            setup_page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            wait_page_ready(setup_page)
            handle_cookie_popup(setup_page)

            countries = get_all_countries(setup_page)

        finally:
            setup_context.close()

        if not countries:
            browser.close()
            raise Exception("No countries found from dropdown")

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
