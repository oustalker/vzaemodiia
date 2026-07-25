from playwright.sync_api import sync_playwright
"""Перевірка рольових інтерфейсів у браузері.

    pip install playwright && playwright install chromium
    uvicorn app.main:app --port 8111      # в іншому терміналі
    python ui_test.py
"""
BASE = "http://127.0.0.1:8111"
ok = fail = 0

def check(label, cond, extra=""):
    global ok, fail
    if cond: ok += 1; print(f"  OK   {label}")
    else: fail += 1; print(f"  FAIL {label} {extra}")

CASES = [
    ("kovalenko", "military",  ".ledger",  ["Журнал потреб", "Спільна дошка", "Хроніка"], ["Дошка пошани", "У мене в роботі"]),
    ("marchenko", "volunteer", ".shift",   ["Дошка запитів", "У мене в роботі", "Дошка пошани"], ["Журнал потреб", "Підтримати"]),
    ("lysenko",   "civilian",  ".impact",  ["Підтримати", "Що зараз потрібно", "Що відбувається"], ["Журнал потреб", "У мене в роботі"]),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    for user, role, marker, present, absent in CASES:
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(BASE, wait_until="networkidle")
        page.fill("#g-username", user); page.fill("#g-password", "demo1234")
        page.click("#gate-form button[type=submit]")
        page.wait_for_selector(".rail-link", timeout=9000)
        page.wait_for_timeout(700)
        print(f"\n[{role}]")
        check("тему застосовано", page.get_attribute("html", "data-role") == role,
              page.get_attribute("html", "data-role"))
        check("рідний блок головного екрана", page.locator(marker).count() > 0)
        nav = page.locator(".rail-link").all_text_contents()
        nav = " | ".join(t.strip().split("\n")[0] for t in nav)
        for item in present:
            check(f"є розділ «{item}»", item in nav, nav)
        for item in absent:
            check(f"немає розділу «{item}»", item not in nav, nav)
        # чужий маршрут не відкривається
        page.goto(f"{BASE}/#/leaders" if role == "military" else f"{BASE}/#/ledger", wait_until="networkidle")
        page.wait_for_timeout(800)
        check("чужий маршрут відкидає на свій екран", page.locator(marker).count() > 0)
        # фон реально різний
        bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
        print(f"       фон: {bg}")
        page.close()
    b.close()

print(f"\n=== пройдено {ok}, провалено {fail} ===")
raise SystemExit(1 if fail else 0)
