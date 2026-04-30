import csv
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ==========================================================
# CONFIG
# ==========================================================

COUNTRY_URLS = [
    "https://www.se.com/ae/en/work/products/tools/ups_selector/",
    "https://www.se.com/africa/fr/work/products/tools/ups_selector/",
    "https://www.se.com/ar/es/work/products/tools/ups_selector/",
    "https://www.se.com/at/de/work/products/tools/ups_selector/",
    "https://www.se.com/au/en/work/products/tools/ups_selector/",
    "https://www.se.com/be/en/work/products/tools/ups_selector/",
    "https://www.se.com/be/fr/work/products/tools/ups_selector/",
    "https://www.se.com/be/nl/work/products/tools/ups_selector/",
    "https://www.se.com/bg/bg/work/products/tools/ups_selector/",
    "https://www.se.com/br/pt/work/products/tools/ups_selector/",
    "https://www.se.com/ca/en/work/products/tools/ups_selector/",
    "https://www.se.com/ca/fr/work/products/tools/ups_selector/",
    "https://www.se.com/ch/de/work/products/tools/ups_selector/",
    "https://www.se.com/ch/fr/work/products/tools/ups_selector/",
    "https://www.se.com/cl/es/work/products/tools/ups_selector/",
    "https://www.se.com/co/es/work/products/tools/ups_selector/",
    "https://www.se.com/cr/es/work/products/tools/ups_selector/",
    "https://www.se.com/cz/cs/work/products/tools/ups_selector/",
    "https://www.se.com/de/de/work/products/tools/ups_selector/",
    "https://www.se.com/dk/da/work/products/tools/ups_selector/",
    "https://www.se.com/dz/fr/work/products/tools/ups_selector/",
    "https://www.se.com/ee/et/work/products/tools/ups_selector/",
    "https://www.se.com/eg/ar/work/products/tools/ups_selector/",
    "https://www.se.com/es/es/work/products/tools/ups_selector/",
    "https://www.se.com/fi/fi/work/products/tools/ups_selector/",
    "https://www.se.com/fr/fr/work/products/tools/ups_selector/",
    "https://www.se.com/gr/el/work/products/tools/ups_selector/",
    "https://www.se.com/hr/hr/work/products/tools/ups_selector/",
    "https://www.se.com/hu/hu/work/products/tools/ups_selector/",
    "https://www.se.com/id/id/work/products/tools/ups_selector/",
    "https://www.se.com/ie/en/work/products/tools/ups_selector/",
    "https://www.se.com/il/he/work/products/tools/ups_selector/",
    "https://www.se.com/in/en/work/products/tools/ups_selector/",
    "https://www.se.com/it/it/work/products/tools/ups_selector/",
    "https://www.se.com/jp/ja/work/products/tools/ups_selector/",
    "https://www.se.com/kr/ko/work/products/tools/ups_selector/",
    "https://www.se.com/lv/lv/work/products/tools/ups_selector/",
    "https://www.se.com/mx/es/work/products/tools/ups_selector/",
    "https://www.se.com/my/en/work/products/tools/ups_selector/",
    "https://www.se.com/nl/nl/work/products/tools/ups_selector/",
    "https://www.se.com/no/no/work/products/tools/ups_selector/",
    "https://www.se.com/nz/en/work/products/tools/ups_selector/",
    "https://www.se.com/pe/es/work/products/tools/ups_selector/",
    "https://www.se.com/ph/en/work/products/tools/ups_selector/",
    "https://www.se.com/pl/pl/work/products/tools/ups_selector/",
    "https://www.se.com/pt/pt/work/products/tools/ups_selector/",
    "https://www.se.com/ro/ro/work/products/tools/ups_selector/",
    "https://www.se.com/sa/ar/work/products/tools/ups_selector/",
    "https://www.se.com/se/sv/work/products/tools/ups_selector/",
    "https://www.se.com/sg/en/work/products/tools/ups_selector/",
    "https://www.se.com/si/sl/work/products/tools/ups_selector/",
    "https://www.se.com/th/th/work/products/tools/ups_selector/",
    "https://www.se.com/tr/tr/work/products/tools/ups_selector/",
    "https://www.se.com/tw/zh/work/products/tools/ups_selector/",
    "https://www.se.com/ua/uk/work/products/tools/ups_selector/",
    "https://www.se.com/uk/en/work/products/tools/ups-selector/",
    "https://www.se.com/us/en/work/products/tools/ups_selector/",
    "https://www.se.com/vn/vi/work/products/tools/ups_selector/",
    "https://www.schneider-electric.cn/zh/work/products/tools/ups_selector/",
]

ENTRIES = [
    {
        "name": "Up to 450W",
        "path": "home/entry",
    },
    {
        "name": "Up to 750W",
        "path": "home/advanced",
    },
    {
        "name": "Up to 1320W",
        "path": "home/performance",
    },
    {
        "name": "Server / Configure by load 20KW",
        "path": "server/load",
    },
]

HEADLESS = False
SLOW_MO = 50
TIMEOUT = 60000

SCREENSHOT_DIR = "screenshots"
REPORT_FILE = "ups_selector_final_report.csv"


# ==========================================================
# BASIC HELPERS
# ==========================================================

def create_folder(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)


def clean_filename(value):
    value = re.sub(r"[^a-zA-Z0-9_-]", "_", value)
    return value[:120]


def normalize_base_url(url):
    return url if url.endswith("/") else url + "/"


def build_result_url(base_url, path):
    return normalize_base_url(base_url) + path


def get_country_code(url):
    parsed = urlparse(url)

    if "schneider-electric.cn" in parsed.netloc:
        return "cn-zh"

    parts = parsed.path.strip("/").split("/")

    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"

    return parsed.netloc.replace(".", "_")


def save_screenshot(page, country, entry_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{country}_{clean_filename(entry_name)}_{timestamp}.png"
    path = os.path.join(SCREENSHOT_DIR, filename)

    try:
        page.screenshot(path=path, full_page=True)
        return path
    except Exception:
        return ""


# ==========================================================
# PAGE HELPERS
# ==========================================================

def wait_for_page(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass

    page.wait_for_timeout(3000)


def handle_cookie_popup(page):
    selectors = [
        "#onetrust-accept-btn-handler",
        "button[id*='accept']",
        "button[class*='accept']",
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        "button:has-text('OK')",
        "button:has-text('Accepter')",
        "button:has-text('Aceptar')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Accetta')",
        "button:has-text('Aceitar')",
        "button:has-text('同意')",
        "button:has-text('接受')",
        "button:has-text('すべて許可')",
        "button:has-text('동의')",
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)

            if locator.count() > 0 and locator.first.is_visible(timeout=1000):
                locator.first.click(timeout=3000)
                page.wait_for_timeout(1000)
                print("  ✓ Cookie popup handled")
                return
        except Exception:
            continue


def scroll_down(page):
    try:
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(800)
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(800)
    except Exception:
        pass


# ==========================================================
# VALIDATION
# ==========================================================

def is_expected_result_page(page, expected_path):
    current_url = page.url.lower()
    expected_path = expected_path.lower()

    if expected_path in current_url:
        return True, f"Expected result path opened: {expected_path}"

    return False, f"Expected path not opened. Expected: {expected_path}, Current URL: {page.url}"


def detect_no_result_text(page):
    try:
        body_text = page.locator("body").inner_text(timeout=5000).lower()
    except Exception:
        return False, ""

    no_result_texts = [
        "0 results",
        "no results",
        "nothing found",
        "no products",
        "no product found",
        "aucun résultat",
        "aucun produit",
        "keine ergebnisse",
        "keine produkte",
        "sin resultados",
        "sin productos",
        "nessun risultato",
        "nessun prodotto",
        "nenhum resultado",
        "nenhum produto",
        "geen resultaten",
        "geen producten",
        "brak wyników",
        "нет результатов",
        "результатів не знайдено",
        "結果がありません",
        "検索結果がありません",
        "검색 결과가 없습니다",
        "ไม่มีผลลัพธ์",
        "không có kết quả",
        "không tìm thấy",
        "没有结果",
        "未找到结果",
        "無結果",
    ]

    for text in no_result_texts:
        if text in body_text:
            return True, text

    return False, ""


def detect_visible_products(page):
    """
    Strong product validation.

    PASS only when visible product/card/product link is detected.
    It avoids PASS only from generic page text like APC, UPS, VA.
    """

    page.wait_for_timeout(4000)
    scroll_down(page)

    no_result, no_result_word = detect_no_result_text(page)
    if no_result:
        return False, 0, f"No-result text detected: {no_result_word}"

    product_selectors = [
        "[data-testid*='product']",
        "[data-test*='product']",
        "[class*='product-card']",
        "[class*='ProductCard']",
        "[class*='productCard']",
        "[class*='product-tile']",
        "[class*='productTile']",
        "[class*='product'] a[href]",
        "[class*='Product'] a[href]",
        "[class*='result'] a[href]",
        "[class*='Result'] a[href]",
        "article a[href]",
        "li a[href]",
        "a[href*='/product/']",
        "a[href*='/products/']",
        "a[href*='back-ups']",
        "a[href*='easy-ups']",
        "a[href*='smart-ups']",
        "a[href*='apc']",
        "a[href*='bx']",
        "a[href*='br']",
        "a[href*='be']",
        "a[href*='smt']",
        "a[href*='srt']",
        "a[href*='sua']",
    ]

    product_hints = [
        "apc",
        "ups",
        "back-ups",
        "back ups",
        "easy-ups",
        "easy ups",
        "smart-ups",
        "smart ups",
        "battery backup",
        "uninterruptible",
        "va",
        "watt",
        "bx",
        "br",
        "be",
        "smt",
        "srt",
        "sua",
    ]

    ignore_hints = [
        "privacy",
        "cookie",
        "terms",
        "condition",
        "contact",
        "support",
        "facebook",
        "linkedin",
        "youtube",
        "twitter",
        "instagram",
        "login",
        "register",
        "download",
        "where to buy",
        "careers",
        "newsroom",
        "sitemap",
        "unsubscribe",
    ]

    found = []
    seen = set()

    for selector in product_selectors:
        try:
            items = page.locator(selector)
            count = items.count()

            for i in range(min(count, 50)):
                try:
                    item = items.nth(i)

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

                    combined = f"{text} {href}".strip().lower()

                    if not combined:
                        continue

                    if any(bad in combined for bad in ignore_hints):
                        continue

                    if not any(hint in combined for hint in product_hints):
                        continue

                    key = combined[:300]

                    if key not in seen:
                        seen.add(key)
                        found.append(combined)

                except Exception:
                    continue

        except Exception:
            continue

    if found:
        return True, len(found), f"Visible product/card links detected: {len(found)}"

    return False, 0, "No visible product cards/product links detected"


# ==========================================================
# TEST ONE ENTRY
# ==========================================================

def test_entry(page, base_url, country, entry_data):
    entry_name = entry_data["name"]
    expected_path = entry_data["path"]
    result_url = build_result_url(base_url, expected_path)

    print("\n==================================================")
    print(f"Country: {country}")
    print(f"Entry  : {entry_name}")
    print("==================================================")

    status = "FAIL"
    results_page_opened = "NO"
    products_detected = 0
    reason = ""
    screenshot = ""
    final_url = ""

    try:
        print(f"  Opening result URL: {result_url}")

        page.goto(result_url, wait_until="domcontentloaded", timeout=TIMEOUT)
        wait_for_page(page)
        handle_cookie_popup(page)

        opened, opened_reason = is_expected_result_page(page, expected_path)

        if opened:
            results_page_opened = "YES"
        else:
            results_page_opened = "NO"

        products_found, products_detected, product_reason = detect_visible_products(page)

        final_url = page.url

        if opened and products_found:
            status = "PASS"
            reason = product_reason
        elif not opened:
            status = "FAIL"
            reason = opened_reason
        else:
            status = "FAIL"
            reason = product_reason

        screenshot = save_screenshot(page, country, entry_name)

        print(f"  Results Page Opened: {results_page_opened}")
        print(f"  Products Detected  : {products_detected}")
        print(f"  Status             : {status}")
        print(f"  Reason             : {reason}")
        print(f"  Final URL          : {final_url}")
        print(f"  Screenshot         : {screenshot}")

    except PlaywrightTimeoutError:
        status = "FAIL"
        reason = "Page load timeout"
        final_url = page.url
        screenshot = save_screenshot(page, country, entry_name)

        print("  Status             : FAIL")
        print(f"  Reason             : {reason}")

    except Exception as e:
        status = "FAIL"
        reason = f"Exception: {str(e)}"
        final_url = page.url
        screenshot = save_screenshot(page, country, entry_name)

        print("  Status             : FAIL")
        print(f"  Reason             : {reason}")

    return [
        country,
        entry_name,
        status,
        results_page_opened,
        products_detected,
        reason,
        final_url,
        screenshot,
    ]


# ==========================================================
# MAIN
# ==========================================================

def main():
    create_folder(SCREENSHOT_DIR)

    with open(REPORT_FILE, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)

        writer.writerow([
            "Country",
            "Entry",
            "Status",
            "Results Page Opened",
            "Products Detected",
            "Reason",
            "Final URL",
            "Screenshot",
        ])

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=HEADLESS,
                slow_mo=SLOW_MO,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            context = browser.new_context(
                viewport={"width": 1440, "height": 1200},
                ignore_https_errors=True,
            )

            page = context.new_page()
            page.set_default_timeout(15000)

            total = len(COUNTRY_URLS) * len(ENTRIES)
            current = 0

            for base_url in COUNTRY_URLS:
                base_url = normalize_base_url(base_url)
                country = get_country_code(base_url)

                for entry_data in ENTRIES:
                    current += 1

                    print(f"\n[{current}/{total}] Testing {country} - {entry_data['name']}")

                    row = test_entry(page, base_url, country, entry_data)
                    writer.writerow(row)
                    csv_file.flush()

            context.close()
            browser.close()

    print("\n==================================================")
    print("TEST COMPLETED")
    print(f"CSV Report  : {REPORT_FILE}")
    print(f"Screenshots : {SCREENSHOT_DIR}")
    print("==================================================")


if __name__ == "__main__":
    main()
