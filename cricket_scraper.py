
import time
import json
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ------------------ CONFIG ------------------
OUTPUT_DIR = Path("cricket_scrape_output")
OUTPUT_DIR.mkdir(exist_ok=True)
JSON_FILE = OUTPUT_DIR / "commentary.json"
MATCHES_FILE = OUTPUT_DIR / "matches.json"

POLL_INTERVAL = 20     # seconds between checks
TIMEOUT = 20           # selenium wait timeout
# ---------------------------------------------

def make_driver(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_matches_list(driver):
    """Scrape matches and categorize as LIVE, UPCOMING, COMPLETED"""
    driver.get("https://www.espncricinfo.com/live-cricket-score")
    wait = WebDriverWait(driver, TIMEOUT)

    matches = {"LIVE": [], "UPCOMING": [], "COMPLETED": []}

    try:
        # All match cards (LIVE + COMPLETED)
        cards = wait.until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.ds-px-4.ds-py-3")
        ))

        for c in cards:
            try:
                title = c.find_element(By.CSS_SELECTOR, "p.ds-text-tight-m").text.strip()
                status = c.find_element(By.CSS_SELECTOR, "span.ds-text-tight-xs").text.strip()
                url = c.find_element(By.CSS_SELECTOR, "a").get_attribute("href")

                if "live" in status.lower():
                    matches["LIVE"].append({"title": title, "status": status, "url": url})
                elif "result" in status.lower() or "stumps" in status.lower():
                    matches["COMPLETED"].append({"title": title, "status": status, "url": url})
                else:
                    matches["UPCOMING"].append({"title": title, "status": status, "url": url})
            except Exception:
                continue

        # Sometimes upcoming matches are in a separate container
        try:
            upcoming_cards = driver.find_elements(By.CSS_SELECTOR, "div.ds-p-4")
            for c in upcoming_cards:
                try:
                    title = c.find_element(By.CSS_SELECTOR, "p.ds-text-tight-m").text.strip()
                    url = c.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                    status = "UPCOMING"
                    if not any(m["title"] == title for m in matches["UPCOMING"]):
                        matches["UPCOMING"].append({"title": title, "status": status, "url": url})
                except Exception:
                    continue
        except Exception:
            pass

    except Exception as e:
        print(f"⚠️ Could not fetch matches: {e}")

    # Save matches to file
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)

    # Console output
    for k, v in matches.items():
        print(f"\n=== {k} MATCHES ({len(v)}) ===")
        for m in v:
            print(f"- {m['title']} ({m['status']}) -> {m['url']}")

    return matches

def scrape_commentary(driver):
    """Scrape live commentary"""
    wait = WebDriverWait(driver, TIMEOUT)
    commentary_texts = []

    possible_selectors = [
        "div.ds-p-3",       # latest Cricinfo layout container
        "div.ds-text-typo", # fallback older layout
    ]

    for sel in possible_selectors:
        try:
            container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            items = container.find_elements(By.CSS_SELECTOR, "*")
            for it in items:
                t = it.text.strip()
                if t and t not in commentary_texts:
                    commentary_texts.append(t)
            if commentary_texts:
                break
        except Exception:
            continue
    return commentary_texts

def load_existing():
    if JSON_FILE.exists():
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main(headless=False):
    driver = make_driver(headless=headless)
    try:
        print("Fetching matches list...")
        matches = get_matches_list(driver)

        if not any(matches.values()):
            print("❌ No matches found! Exiting.")
            return

        # Prefer live, else completed
        match = None
        if matches["LIVE"]:
            match = matches["LIVE"][0]
        elif matches["COMPLETED"]:
            match = matches["COMPLETED"][0]
        else:
            print("❌ No live or completed match found! Exiting.")
            return

        print(f"\n📌 Selected match: {match['title']} ({match['status']})")
        driver.get(match["url"])
        match_title = driver.title

        # Save screenshot once only
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        driver.save_screenshot(str(OUTPUT_DIR / f"commentary_{ts}.png"))

        all_data = load_existing()
        seen = set(d["text"] for d in all_data)

        print("\nScraper started. Press Ctrl+C to stop.")

        while True:
            try:
                commentary_texts = scrape_commentary(driver)
                new_entries = [t for t in commentary_texts if t not in seen]

                if new_entries:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] New commentary found!")
                    for t in new_entries:
                        entry = {
                            "timestamp": datetime.now().isoformat(),
                            "match": match_title,
                            "text": t,
                        }
                        all_data.append(entry)
                        seen.add(t)
                    save_data(all_data)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No new commentary.")

            except Exception as e:
                print(f"⚠️ Error fetching commentary: {e}")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main(headless=False)
