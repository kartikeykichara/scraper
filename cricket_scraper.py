import requests, re, time, json
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime

BASE, SCORES_URL = "https://www.cricbuzz.com", "https://www.cricbuzz.com/live-cricket-scores"
OUTPUT_DIR = Path("cricbuzz_output"); OUTPUT_DIR.mkdir(exist_ok=True)
MATCHES_FILE = OUTPUT_DIR / "matches.json"
seen_balls = set()
HEADERS = {"User-Agent": "Mozilla/5.0"}

def scrape_matches():
    try:
        resp = requests.get(SCORES_URL, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser") if resp.status_code == 200 else None
        matches = {"live": [], "upcoming": [], "completed": []}
        if not soup: return matches

        for a in soup.select("a.cb-lv-scrs-well"):
            href, text = a.get("href", ""), a.get_text(" ", strip=True)
            m = re.search(r'/live-cricket-scores/(\d+)', href)
            if not m: continue
            match_id = m.group(1)
            cls_text = " ".join(a.get("class", [])).lower()

            # 1 Live match detection
            if "live" in cls_text or re.search(r"trail by|start delayed|Rain stop|Day \d+", text, re.I):
                matches["live"].append({"name": text, "id": match_id, "link": BASE + href})
            # 2 Completed match detection
            elif re.search(r"won by|lead by|innings|overs|all out", text, re.I):
                matches["completed"].append({"name": text, "id": match_id, "link": BASE + href})
            # 3️ Upcoming fallback
            else:
                matches["upcoming"].append({"name": text, "id": match_id, "link": BASE + href})

        return matches
    except Exception as e:
        print(" Error scraping matches:", e)
        return {"live": [], "upcoming": [], "completed": []}

def save_json(data, path):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_commentary(match_id):
    try:
        url = f"{BASE}/api/cricket-match/commentary/{match_id}"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*",
                   "Referer": f"{BASE}/live-cricket-scores/{match_id}"}
        resp = requests.get(url, headers=headers, timeout=10)
        comm_list = resp.json().get("commentaryList", []) if resp.status_code == 200 else []
        new_data = []
        for c in comm_list:
            ball = c.get("ballNbr")
            if ball and ball not in seen_balls:
                seen_balls.add(ball)
                new_data.append({
                    "desc": c.get("commText"), "over": c.get("overNumber"),
                    "event": c.get("event"), "batsman": c.get("batsmanStriker", {}).get("batName"),
                    "bowler": c.get("bowlerStriker", {}).get("bowlName"), "score": c.get("batTeamScore"),
                    "time": datetime.now().strftime("%H:%M:%S")
                })
        return new_data
    except Exception as e:
        print(" Error fetching commentary:", e)
        return []

# -----------------------------
if __name__ == "__main__":
    matches = scrape_matches()
    save_json(matches, MATCHES_FILE)

    idx_map, idx = {}, 1
    print("\n Matches:")
    for cat in ["live", "upcoming", "completed"]:
        print(f"\n=== {cat.upper()} ===")
        for m in matches[cat]:
            print(f"{idx}. {m['name']} | ID: {m['id']}")
            idx_map[idx] = m["id"]; idx += 1

    try:
        choice = int(input("\n Enter match number to track commentary: "))
        match_id = idx_map[choice]
    except:
        print(" Invalid choice."); exit()

    output_file = OUTPUT_DIR / f"match_{match_id}_commentary.json"
    while True:
        new_entries = fetch_commentary(match_id)
        if new_entries:
            old = json.loads(output_file.read_text(encoding="utf-8")) if output_file.exists() else []
            old.extend(new_entries)
            save_json(old, output_file)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(new_entries)} new entries saved")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No new commentary yet...")
        time.sleep(30)
