from playwright.sync_api import sync_playwright
from datetime import datetime
import os
import csv
import re


# ==========================================================
# CONFIG
# ==========================================================

BASE_URL = "https://dellups.com/ups-selector/"

OUTPUT_DIR = "dell_ups_test_output"
SCREENSHOT_DIR = os.path.join(OUTPUT_DIR, "screenshots")

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_FILE = os.path.join(OUTPUT_DIR, f"dell_ups_results_{RUN_ID}.csv")

CSV_COLUMNS = [
    "Country",
    "Results Page Opened",
    "Status",
    "Reason",
    "Continue Clicked",
    "Products Count",
    "Screenshot",
]


# ==========================================================
# HELPERS
# ==========================================================

def safe_name(name):
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name


def save_screenshot(page, country, step):
    file_name = f"{safe_name(country)}_{step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    path = os.path.join(SCREENSHOT_DIR, file_name)

    try:
        page.screenshot(path=path, full_page=True)
        print(f"  📸 Screenshot saved: {path}")
        return path
    except Exception as e:
        print(f"  ⚠ Screenshot failed: {e}")
        return ""


def wait_page(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except:
        pass

    page.wait_for_timeout(1500)


def scroll_down(page, times=4, distance=500):
    for _ in range(times):
        page.mouse.wheel(0, distance)
        page.wait_for_timeout(400)


def get_text(el):
    try:
        text = el.inner_text(timeout=1000).strip()
        if text:
            return text
    except:
        pass

    try:
        return el.evaluate("""
            e => (
                e.innerText ||
                e.textContent ||
                e.value ||
                e.getAttribute('aria-label') ||
                e.getAttribute('title') ||
                ''
            ).trim()
        """)
    except:
        return ""


def is_blue_button(el):
    """
    Dell Continue button is blue/cyan.
    Example: rgb(66, 180, 230)
    """
    try:
        bg = el.evaluate("e => window.getComputedStyle(e).backgroundColor")
        nums = re.findall(r"\d+", bg)

        if len(nums) < 3:
            return False, bg

        r = int(nums[0])
        g = int(nums[1])
        b = int(nums[2])

        is_blue = b >= 120 and g >= 100 and r <= 180

        return is_blue, bg

    except:
        return False, ""


def handle_cookie_popup(page):
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('I Accept')",
        "button:has-text('OK')",
        "button:has-text('Agree')",
        "button:has-text('Allow all')",
    ]

    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                btn.click(timeout=5000)
                page.wait_for_timeout(1000)
                print(f"  ✅ Cookie popup handled: {selector}")
                return True
        except:
            pass

    return False


# ==========================================================
# COUNTRY DROPDOWN
# ==========================================================

def get_all_countries(page):
    print("\n📋 Reading countries from dropdown...")

    dropdown = page.locator("select").first
    dropdown.wait_for(state="visible", timeout=10000)

    countries = []
    options = dropdown.locator("option")

    for i in range(options.count()):
        label = options.nth(i).inner_text().strip()
        value = options.nth(i).get_attribute("value") or ""

        if not label:
            continue

        label_lower = label.lower()

        if label_lower in ["select", "select country", "choose country", "country"]:
            continue

        if "select" in label_lower and not value:
            continue

        countries.append(label)

    print(f"✅ Countries found: {len(countries)}")
    return countries


def select_country(page, country):
    print(f"  🌍 Selecting country: {country}")

    dropdown = page.locator("select").first
    dropdown.wait_for(state="visible", timeout=10000)

    try:
        dropdown.select_option(label=country)
        page.wait_for_timeout(3000)
        print("  ✅ Country selected")
        return True
    except Exception as e:
        print(f"  ❌ Country selection failed: {e}")
        return False


# ==========================================================
# CLICK CONTINUE BUTTON
# ==========================================================

def click_continue_button(page, country):
    """
    Final practical logic:
    - After country selection, scroll down.
    - Click visible Dell blue button inside page body.
    - Do not click Select Your Region / menu buttons.
    - Empty text is allowed because Dell Continue button sometimes shows empty in DOM.
    """

    print("  ➡ Looking for blue Continue button...")

    page.wait_for_timeout(2000)

    scroll_down(page, times=5, distance=450)

    elements = page.locator(
        "button, input[type='button'], input[type='submit'], a[role='button']"
    )

    blocked_texts = [
        "select your region",
        "products",
        "software and services",
        "resources",
        "contact",
        "support",
        "menu",
        "filter by",
        "change requirements",
    ]

    candidates = []

    total = elements.count()
    print(f"  Total button-like elements found: {total}")

    for i in range(total):
        try:
            el = elements.nth(i)

            if not el.is_visible(timeout=1000):
                continue

            if not el.is_enabled(timeout=1000):
                continue

            box = el.bounding_box()
            if not box:
                continue

            if box["width"] < 70 or box["height"] < 25:
                continue

            text = get_text(el).strip()
            text_lower = text.lower()

            is_blue, bg = is_blue_button(el)

            print(
                f"    Button: text='{text}' blue={is_blue} bg='{bg}' "
                f"x={round(box['x'],1)} y={round(box['y'],1)} "
                f"w={round(box['width'],1)} h={round(box['height'],1)}"
            )

            if text_lower and any(bad in text_lower for bad in blocked_texts):
                print(f"    Skipped blocked button: '{text}'")
                continue

            if not is_blue:
                continue

            # Avoid top/header area. Continue button is in page body.
            if box["y"] < 100:
                continue

            candidates.append({
                "element": el,
                "text": text,
                "box": box,
                "bg": bg,
            })

        except Exception as e:
            print(f"    ⚠ Button check failed: {e}")

    if not candidates:
        print("  ❌ No blue Continue button found")
        save_screenshot(page, country, "continue_not_found")
        return False

    # Pick top-most blue button in body content.
    candidates.sort(key=lambda x: x["box"]["y"])

    btn = candidates[0]
    el = btn["element"]
    text = btn["text"] or "BLUE_CONTINUE_BUTTON"

    try:
        el.scroll_into_view_if_needed(timeout=5000)
        page.wait_for_timeout(500)

        save_screenshot(page, country, "before_continue_click")

        el.click(timeout=10000)

        print(f"  ✅ Continue clicked: text='{text}', bg='{btn['bg']}'")

        page.wait_for_timeout(5000)
        wait_page(page)

        return True

    except Exception as e:
        print(f"  ❌ Continue click failed: {e}")
        save_screenshot(page, country, "continue_click_failed")
        return False


# ==========================================================
# RESULT VALIDATION
# ==========================================================

def verify_results(page, country):
    """
    Validation:
    - FAIL only for real no-result pages:
      0 Results / 0 Ergebnisse / Nothing found / no results found
    - PASS for product pages:
      50 Results / 50 Ergebnisse / APC Smart-UPS / UPS Batteries / model numbers
    """

    print("  🔎 Verifying product page...")

    page.wait_for_timeout(5000)

    screenshot = save_screenshot(page, country, "result_page")

    try:
        body_text = page.locator("body").inner_text(timeout=10000)
    except:
        body_text = ""

    body_lower = body_text.lower()

    # ======================================================
    # 1. FAIL only when real no-product message is visible
    # IMPORTANT:
    # Do not use plain "0 result" because "50 Results" contains "0 result".
    # ======================================================

    no_result_patterns = [
        r"\b0\s+results?\b",
        r"\b0\s+ergebnisse\b",
        r"\b0\s+résultats?\b",
        r"\b0\s+resultados?\b",
        r"\b0\s+risultati?\b",
        r"\b0\s+resultaten\b",
    ]

    no_result_texts = [
        "nothing found",
        "no results found",
        "no products found",
        "there are no results found",
        "sorry, there are no results found",
        "aucun résultat",
        "aucun produit",
        "sin resultados",
        "sin productos",
        "sem resultados",
        "sem produtos",
        "keine ergebnisse",
        "keine produkte",
        "nessun risultato",
        "nessun prodotto",
        "нет результатов",
        "товары не найдены",
    ]

    for pattern in no_result_patterns:
        if re.search(pattern, body_lower):
            print(f"  ❌ FAIL: Found no-result pattern: {pattern}")
            screenshot = save_screenshot(page, country, "fail_nothing_found")
            return "YES", "FAIL", f"No products: {pattern}", 0, screenshot

    for text in no_result_texts:
        if text in body_lower:
            print(f"  ❌ FAIL: Found no-result text: {text}")
            screenshot = save_screenshot(page, country, "fail_nothing_found")
            return "YES", "FAIL", f"No products: {text}", 0, screenshot

    # ======================================================
    # 2. PASS if result count is visible
    # Examples:
    # 50 Results
    # 50 Ergebnisse für 200 W
    # ======================================================

    count_patterns = [
        r"\b(\d+)\s+results?\b",
        r"\b(\d+)\s+ergebnisse\b",
        r"\b(\d+)\s+résultats?\b",
        r"\b(\d+)\s+resultados?\b",
        r"\b(\d+)\s+risultati?\b",
        r"\b(\d+)\s+resultaten\b",
    ]

    for pattern in count_patterns:
        match = re.search(pattern, body_lower)
        if match:
            products_count = int(match.group(1))

            if products_count > 0:
                print(f"  ✅ PASS: Product count found: {products_count}")
                screenshot = save_screenshot(page, country, "pass_product_count")
                return "YES", "PASS", f"Products found: {products_count}", products_count, screenshot

    # ======================================================
    # 3. PASS if known product text is visible
    # ======================================================

    product_text_words = [
        "apc smart-ups",
        "smart-ups",
        "easy ups",
        "easy-ups",
        "back-ups",
        "symmetra",
        "galaxy",
        "ups batteries",
        "ups battery",
        "battery backup",
        "replacement battery",
        "battery cartridge",
        "battery pack",
        "battery cabinet",
        "beste übereinstimmung",
        "best match",
        "ansprechpartner vertrieb",
        "gesamtleistungsaufnahme",
        "überbrückungszeit",
        "maximal verwendete leistung",
    ]

    matched_product_words = []

    for word in product_text_words:
        if word in body_lower:
            matched_product_words.append(word)

    if matched_product_words:
        print(f"  ✅ PASS: Product text found: {matched_product_words}")
        screenshot = save_screenshot(page, country, "pass_product_text")
        return (
            "YES",
            "PASS",
            f"Product text found: {', '.join(matched_product_words[:5])}",
            len(matched_product_words),
            screenshot,
        )

    # ======================================================
    # 4. PASS if product model numbers are visible
    # Examples: SU420INET, SUVS420I, SMT750I, SRT1000XLI
    # ======================================================

    model_patterns = [
        r"\bSU[A-Z0-9]{3,}\b",
        r"\bSUA[A-Z0-9]{3,}\b",
        r"\bSUVS[A-Z0-9]{3,}\b",
        r"\bSMT[A-Z0-9]{3,}\b",
        r"\bSRT[A-Z0-9]{3,}\b",
        r"\bBX[A-Z0-9]{3,}\b",
        r"\bBR[A-Z0-9]{3,}\b",
    ]

    found_models = []

    for pattern in model_patterns:
        matches = re.findall(pattern, body_text, flags=re.IGNORECASE)
        found_models.extend(matches)

    unique_models = sorted(list(set(found_models)))

    if unique_models:
        print(f"  ✅ PASS: Product model numbers found: {unique_models[:10]}")
        screenshot = save_screenshot(page, country, "pass_model_numbers")
        return (
            "YES",
            "PASS",
            f"Product models found: {', '.join(unique_models[:5])}",
            len(unique_models),
            screenshot,
        )

    # ======================================================
    # 5. PASS if product elements/cards/rows are visible
    # ======================================================

    scroll_down(page, times=3, distance=600)

    product_row_selectors = [
        "text=APC Smart-UPS",
        "text=Smart-UPS",
        "text=Easy UPS",
        "text=Back-UPS",
        "text=Symmetra",
        "text=Galaxy",
        "text=UPS Batteries",
        "text=Ansprechpartner Vertrieb",
        "text=Beste Übereinstimmung",
        "text=Best Match",
        "a[href*='product']",
        "a[href*='ups']",
        "a[href*='battery']",
        "[class*='product']",
        "[class*='Product']",
    ]

    visible_product_elements = 0

    for selector in product_row_selectors:
        try:
            items = page.locator(selector)
            total = items.count()

            for i in range(min(total, 60)):
                try:
                    item = items.nth(i)

                    if item.is_visible(timeout=500):
                        visible_product_elements += 1
                except:
                    pass

        except:
            pass

    if visible_product_elements > 0:
        print(f"  ✅ PASS: Product elements visible: {visible_product_elements}")
        screenshot = save_screenshot(page, country, "pass_product_elements")
        return (
            "YES",
            "PASS",
            f"Product elements visible: {visible_product_elements}",
            visible_product_elements,
            screenshot,
        )

    # ======================================================
    # 6. FINAL FAIL
    # ======================================================

    print("  ❌ FAIL: No product cards/products visible")
    screenshot = save_screenshot(page, country, "fail_no_products_visible")
    return "YES", "FAIL", "No product cards/products visible", 0, screenshot


# ==========================================================
# TEST ONE COUNTRY
# ==========================================================

def test_country(browser, country):
    row = {
        "Country": country,
        "Results Page Opened": "NO",
        "Status": "FAIL",
        "Reason": "",
        "Continue Clicked": "NO",
        "Products Count": 0,
        "Screenshot": "",
    }

    context = browser.new_context(viewport={"width": 1440, "height": 1200})
    page = context.new_page()

    try:
        print(f"\n🌐 Opening fresh page for: {country}")

        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        wait_page(page)

        handle_cookie_popup(page)

        selected = select_country(page, country)

        if not selected:
            row["Reason"] = "Country selection failed"
            row["Screenshot"] = save_screenshot(page, country, "country_selection_failed")
            return row

        save_screenshot(page, country, "after_country_selection")

        clicked = click_continue_button(page, country)

        if not clicked:
            row["Continue Clicked"] = "NO"
            row["Reason"] = "Continue button not clicked"
            row["Screenshot"] = save_screenshot(page, country, "continue_not_clicked")
            return row

        row["Continue Clicked"] = "YES"

        opened, status, reason, count, screenshot = verify_results(page, country)

        row["Results Page Opened"] = opened
        row["Status"] = status
        row["Reason"] = reason
        row["Products Count"] = count
        row["Screenshot"] = screenshot

        return row

    except Exception as e:
        row["Status"] = "FAIL"
        row["Reason"] = f"Unexpected error: {e}"
        row["Screenshot"] = save_screenshot(page, country, "unexpected_error")
        return row

    finally:
        context.close()


# ==========================================================
# CSV
# ==========================================================

def create_csv():
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()


def write_csv_row(row):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writerow(row)


# ==========================================================
# MAIN
# ==========================================================

def main():
    print("==================================================")
    print("Dell UPS Selector - All Countries Test")
    print("==================================================")
    print(f"URL: {BASE_URL}")
    print(f"CSV Report: {CSV_FILE}")
    print(f"Screenshots Folder: {SCREENSHOT_DIR}")

    create_csv()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=100
        )

        # Open once to collect countries
        context = browser.new_context(viewport={"width": 1440, "height": 1200})
        page = context.new_page()

        print(f"\n🌐 Opening page to collect countries: {BASE_URL}")

        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        wait_page(page)
        handle_cookie_popup(page)

        countries = get_all_countries(page)

        context.close()

        if not countries:
            print("\n❌ No countries found. Stopping.")
            browser.close()
            return

        print(f"\n📋 Total countries to test: {len(countries)}")

        pass_count = 0
        fail_count = 0

        for index, country in enumerate(countries, start=1):
            print("\n--------------------------------------------------")
            print(f"[{index}/{len(countries)}] Testing: {country}")
            print("--------------------------------------------------")

            row = test_country(browser, country)
            write_csv_row(row)

            if row["Status"] == "PASS":
                pass_count += 1
                print(f"✅ PASS | {country} | {row['Reason']}")
            else:
                fail_count += 1
                print(f"❌ FAIL | {country} | {row['Reason']}")

        browser.close()

        print("\n==================================================")
        print("TEST COMPLETED")
        print("==================================================")
        print(f"Total countries: {len(countries)}")
        print(f"PASS: {pass_count}")
        print(f"FAIL: {fail_count}")
        print(f"CSV Report: {CSV_FILE}")
        print(f"Screenshots Folder: {SCREENSHOT_DIR}")


if __name__ == "__main__":
    main()
