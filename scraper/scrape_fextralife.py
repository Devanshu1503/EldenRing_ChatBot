"""
Scrapes Fextralife Elden Ring pages and saves as JSON.
Run once: python scraper/scrape_fextralife.py
"""

import httpx
import json
import time
from bs4 import BeautifulSoup
from pathlib import Path

OUT_FILE = Path("data/raw/fextralife.json")

WALKTHROUGH_PAGES = [
    # ── Main guides ───────────────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Walkthrough",
    "https://eldenring.wiki.fextralife.com/Game+Progress+Route",
    "https://eldenring.wiki.fextralife.com/Shadow+of+the+Erdtree+Walkthrough",
    "https://eldenring.wiki.fextralife.com/Side+Quests",
    "https://eldenring.wiki.fextralife.com/Bosses",
    "https://eldenring.wiki.fextralife.com/New+Game+Plus",
    "https://eldenring.wiki.fextralife.com/Endings",

    # ── Legacy dungeons ───────────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Stormveil+Castle",
    "https://eldenring.wiki.fextralife.com/Raya+Lucaria+Academy",
    "https://eldenring.wiki.fextralife.com/Volcano+Manor",
    "https://eldenring.wiki.fextralife.com/Leyndell+Royal+Capital",
    "https://eldenring.wiki.fextralife.com/Crumbling+Farum+Azula",
    "https://eldenring.wiki.fextralife.com/Miquella%27s+Haligtree",
    "https://eldenring.wiki.fextralife.com/Elphael+Brace+of+the+Haligtree",
    "https://eldenring.wiki.fextralife.com/Subterranean+Shunning-Grounds",

    # ── Regions ───────────────────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Limgrave",
    "https://eldenring.wiki.fextralife.com/Weeping+Peninsula",
    "https://eldenring.wiki.fextralife.com/Liurnia+of+the+Lakes",
    "https://eldenring.wiki.fextralife.com/Caelid",
    "https://eldenring.wiki.fextralife.com/Altus+Plateau",
    "https://eldenring.wiki.fextralife.com/Mt+Gelmir",
    "https://eldenring.wiki.fextralife.com/Mountaintops+of+the+Giants",
    "https://eldenring.wiki.fextralife.com/Consecrated+Snowfield",
    "https://eldenring.wiki.fextralife.com/Siofra+River",
    "https://eldenring.wiki.fextralife.com/Ainsel+River",
    "https://eldenring.wiki.fextralife.com/Deeproot+Depths",
    "https://eldenring.wiki.fextralife.com/Nokron+Eternal+City",
    "https://eldenring.wiki.fextralife.com/Mohgwyn+Palace",
    "https://eldenring.wiki.fextralife.com/Moonlight+Altar",

    # ── Small dungeons: Limgrave & Weeping Peninsula ──────────────────────
    "https://eldenring.wiki.fextralife.com/Stormfoot+Catacombs",
    "https://eldenring.wiki.fextralife.com/Murkwater+Cave",
    "https://eldenring.wiki.fextralife.com/Murkwater+Catacombs",
    "https://eldenring.wiki.fextralife.com/Coastal+Cave",
    "https://eldenring.wiki.fextralife.com/Limgrave+Tunnels",
    "https://eldenring.wiki.fextralife.com/Groveside+Cave",
    "https://eldenring.wiki.fextralife.com/Highroad+Cave",
    "https://eldenring.wiki.fextralife.com/Deathtouched+Catacombs",
    "https://eldenring.wiki.fextralife.com/Impaler%27s+Catacombs",
    "https://eldenring.wiki.fextralife.com/Tombsward+Cave",
    "https://eldenring.wiki.fextralife.com/Tombsward+Catacombs",
    "https://eldenring.wiki.fextralife.com/Morne+Tunnel",
    "https://eldenring.wiki.fextralife.com/Earthbore+Cave",

    # ── Small dungeons: Liurnia ───────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Raya+Lucaria+Crystal+Tunnel",
    "https://eldenring.wiki.fextralife.com/Stillwater+Cave",
    "https://eldenring.wiki.fextralife.com/Lakeside+Crystal+Cave",
    "https://eldenring.wiki.fextralife.com/Academy+Crystal+Cave",
    "https://eldenring.wiki.fextralife.com/Roads+End+Catacombs",
    "https://eldenring.wiki.fextralife.com/Black+Knife+Catacombs",
    "https://eldenring.wiki.fextralife.com/Cliffbottom+Catacombs",

    # ── Small dungeons: Caelid ────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Caelid+Catacombs",
    "https://eldenring.wiki.fextralife.com/War-Dead+Catacombs",
    "https://eldenring.wiki.fextralife.com/Sellia+Crystal+Tunnel",
    "https://eldenring.wiki.fextralife.com/Gaol+Cave",
    "https://eldenring.wiki.fextralife.com/Dragonbarrow+Cave",

    # ── Small dungeons: Altus / Mt Gelmir ────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Sainted+Hero%27s+Grave",
    "https://eldenring.wiki.fextralife.com/Auriza+Hero%27s+Grave",
    "https://eldenring.wiki.fextralife.com/Auriza+Side+Tomb",
    "https://eldenring.wiki.fextralife.com/Sage%27s+Cave",
    "https://eldenring.wiki.fextralife.com/Gelmir+Hero%27s+Grave",
    "https://eldenring.wiki.fextralife.com/Volcano+Cave",

    # ── Small dungeons: Mountaintops / Snowfield ──────────────────────────
    "https://eldenring.wiki.fextralife.com/Giants%27+Mountaintop+Catacombs",
    "https://eldenring.wiki.fextralife.com/Consecrated+Snowfield+Catacombs",
    "https://eldenring.wiki.fextralife.com/Cave+of+the+Forlorn",
    "https://eldenring.wiki.fextralife.com/Spiritcaller%27s+Cave",
    "https://eldenring.wiki.fextralife.com/Yelough+Anix+Tunnel",

    # ── Boss strategies ───────────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Margit+the+Fell+Omen",
    "https://eldenring.wiki.fextralife.com/Godrick+the+Grafted",
    "https://eldenring.wiki.fextralife.com/Rennala+Queen+of+the+Full+Moon",
    "https://eldenring.wiki.fextralife.com/Starscourge+Radahn",
    "https://eldenring.wiki.fextralife.com/Morgott+the+Omen+King",
    "https://eldenring.wiki.fextralife.com/Fire+Giant",
    "https://eldenring.wiki.fextralife.com/Maliketh+the+Black+Blade",
    "https://eldenring.wiki.fextralife.com/Godfrey+First+Elden+Lord",
    "https://eldenring.wiki.fextralife.com/Radagon+of+the+Golden+Order",
    "https://eldenring.wiki.fextralife.com/Elden+Beast",
    "https://eldenring.wiki.fextralife.com/Malenia+Blade+of+Miquella",
    "https://eldenring.wiki.fextralife.com/Mohg+Lord+of+Blood",
    "https://eldenring.wiki.fextralife.com/Rykard+Lord+of+Blasphemy",
    "https://eldenring.wiki.fextralife.com/Astel+Naturalborn+of+the+Void",
    "https://eldenring.wiki.fextralife.com/Lichdragon+Fortissax",
    "https://eldenring.wiki.fextralife.com/Dragonlord+Placidusax",

    # ── NPC questlines ────────────────────────────────────────────────────
    "https://eldenring.wiki.fextralife.com/Ranni+the+Witch",
    "https://eldenring.wiki.fextralife.com/Blaidd",
    "https://eldenring.wiki.fextralife.com/Millicent",
    "https://eldenring.wiki.fextralife.com/Alexander",
    "https://eldenring.wiki.fextralife.com/Nepheli+Loux",
    "https://eldenring.wiki.fextralife.com/Fia",
    "https://eldenring.wiki.fextralife.com/Dung+Eater",
    "https://eldenring.wiki.fextralife.com/Patches",
    "https://eldenring.wiki.fextralife.com/Boc+the+Seamster",
    "https://eldenring.wiki.fextralife.com/Hyetta",
    "https://eldenring.wiki.fextralife.com/White+Mask+Varre",
    "https://eldenring.wiki.fextralife.com/Roderika",
    "https://eldenring.wiki.fextralife.com/Sorcerer+Rogier",
    "https://eldenring.wiki.fextralife.com/Preceptor+Seluvis",
    "https://eldenring.wiki.fextralife.com/Sellen",
    "https://eldenring.wiki.fextralife.com/Gowry",
    "https://eldenring.wiki.fextralife.com/Goldmask",
    "https://eldenring.wiki.fextralife.com/Brother+Corhyn",
    "https://eldenring.wiki.fextralife.com/Yura",
    "https://eldenring.wiki.fextralife.com/Jar-Bairn",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
        tag.decompose()
    content = soup.find(id="wiki-content") or soup.find("div", class_="wiki-content") or soup
    return " ".join(content.get_text(separator=" ").split())


def scrape() -> list[dict]:
    pages = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        for url in WALKTHROUGH_PAGES:
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    print(f"  SKIP {url} ({resp.status_code})")
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title else url
                text = extract_text(soup)
                if len(text) > 100:
                    pages.append({"url": url, "title": title, "text": text, "source": "fextralife"})
                    print(f"  OK  [{len(pages):>3}] {title[:60]}")
                else:
                    print(f"  EMPTY {url}")
            except Exception as e:
                print(f"  ERROR {url}: {e}")
            time.sleep(1)
    return pages


if __name__ == "__main__":
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print(f"Scraping {len(WALKTHROUGH_PAGES)} Fextralife pages ...")
    pages = scrape()
    OUT_FILE.write_text(json.dumps(pages, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. {len(pages)} pages saved to {OUT_FILE}")
