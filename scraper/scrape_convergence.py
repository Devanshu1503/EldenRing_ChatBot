"""
Crawls convergencemod.com and saves all page content as JSON.
Run once: python scraper/scrape_convergence.py
"""

import httpx
import json
import time
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.convergencemod.com"
OUT_FILE = Path("data/raw/convergence.json")

SEED_PATHS = [
    "/classes/",
    "/weapons/",
    "/spells/",
    "/equipment/",
    "/items/",
    "/bosses/",
    "/enemies/",
    "/quests/",
    "/merchants/",
    "/teleporters/",
    "/changelogs/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".pdf", ".zip", ".mp4"}

def collect_links(soup: BeautifulSoup, current_url: str) -> list[str]:
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(current_url, href)
        parsed = urlparse(full)
        if parsed.netloc != "www.convergencemod.com":
            continue
        if parsed.scheme not in ("http", "https"):
            continue
        if "wp-content/uploads" in full:
            continue
        ext = "." + full.split(".")[-1].lower().split("/")[0] if "." in full.split("/")[-1] else ""
        if ext in SKIP_EXTENSIONS:
            continue
        links.append(full.split("#")[0].rstrip("/") + "/")
    return list(set(links))


def scrape() -> list[dict]:
    visited = set()
    to_visit = [BASE_URL + p for p in SEED_PATHS]
    pages = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        while to_visit:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    print(f"  SKIP {url} ({resp.status_code})")
                    continue
            except Exception as e:
                print(f"  ERROR {url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title else url
            text = extract_text(soup)

            if len(text) > 100:
                pages.append({"url": url, "title": title, "text": text})
                print(f"  OK  [{len(pages):>3}] {title[:60]}")

            for link in collect_links(soup, url):
                if link not in visited:
                    to_visit.append(link)

            time.sleep(0.5)

    return pages


if __name__ == "__main__":
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    print("Scraping convergencemod.com ...")
    pages = scrape()
    OUT_FILE.write_text(json.dumps(pages, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. {len(pages)} pages saved to {OUT_FILE}")
