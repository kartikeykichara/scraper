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

def get_first_live_match(driver):
    """Grab first live match URL from Cricinfo live scores page"""
    driver.get("https://www.espncricinfo.com/live-cricket-score")
    wait = WebDriverWait(driver, TIMEOUT)
    try:
        link = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "a.ds-no-tap-higlight")  # match links container
        ))
        url = link.get_attribute("href")
        return url
    except Exception:
        return None

def scrape_commentary(driver):
    """Scrape live commentary"""
    wait = WebDriverWait(driver, TIMEOUT)
    commentary_texts = []

    possible_selectors = [
        "div.ds-p-3",  # latest Cricinfo layout container
        "div#wzrk_wrapper",  # fallback older layout
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
        print("Fetching first live match URL...")
        match_url = get_first_live_match(driver)
        if not match_url:
            print("No live match found!")
            return

        print(f"Live match URL found: {match_url}")
        driver.get(match_url)
        match_title = driver.title

        all_data = load_existing()
        seen = set(d["text"] for d in all_data)

        print("Scraper started. Press Ctrl+C to stop.")

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

                    # Save screenshot
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    driver.save_screenshot(str(OUTPUT_DIR / f"commentary_{ts}.png"))
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
