"""Scrape SHL Individual Test Solutions catalog from shl.com."""
import __future__

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE = "https://www.shl.com"
LIST_URL = BASE + "/products/product-catalog/"
DETAIL_PREFIX = "/solutions/products/product-catalog/view/"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "catalog.json"

TEST_TYPE_MAP = {
    "A": "Ability & Aptitude",
    "B": "Biodata & Situational Judgement",
    "C": "Competencies",
    "D": "Development & 360",
    "E": "Assessment Exercises",
    "K": "Knowledge & Skills",
    "P": "Personality & Behavior",
    "S": "Simulations",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_page(client: httpx.Client, url: str) -> str:
    for attempt in range(3):
        try:
            resp = client.get(url, headers=HEADERS, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning("Attempt %d failed for %s: %s", attempt + 1, url, e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after 3 attempts")


def parse_list_row(tr) -> dict | None:
    """Parse a single <tr> from the Individual Test Solutions table."""
    link = tr.select_one("td.custom__table-heading__title a")
    if not link:
        return None
    name = link.get_text(strip=True)
    href = link.get("href", "")
    slug = href.strip("/").split("/")[-1] if href else ""
    url = urljoin(BASE + "/", href.lstrip("/"))

    # Remote testing
    remote_td = tr.select("td.custom__table-heading__general")[0] if len(tr.select("td.custom__table-heading__general")) >= 1 else None
    remote_testing = bool(remote_td and remote_td.select_one("span.catalogue__circle.-yes")) if remote_td else False

    # Adaptive/IRT
    adaptive_td = tr.select("td.custom__table-heading__general")[1] if len(tr.select("td.custom__table-heading__general")) >= 2 else None
    adaptive_irt = bool(adaptive_td and adaptive_td.select_one("span.catalogue__circle.-yes")) if adaptive_td else False

    # Test type keys
    keys_td = tr.select_one("td.product-catalogue__keys")
    test_types = []
    if keys_td:
        for span in keys_td.select("span.product-catalogue__key"):
            key = span.get_text(strip=True)
            if key in TEST_TYPE_MAP:
                test_types.append(key)

    entity_id = tr.get("data-entity-id", "")

    return {
        "name": name,
        "slug": slug,
        "url": url,
        "remote_testing": remote_testing,
        "adaptive_irt": adaptive_irt,
        "test_type_keys": test_types,
        "test_types": [TEST_TYPE_MAP.get(k, k) for k in test_types],
        "entity_id": entity_id,
    }


def parse_detail_page(html: str, item: dict) -> dict:
    """Enrich item with detail page data: description, job levels, languages, duration."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(".product-catalogue-training-calendar__row")

    description = ""
    job_levels = ""
    languages = ""
    duration_minutes = None

    for row in rows:
        h4 = row.select_one("h4")
        if not h4:
            continue
        header = h4.get_text(strip=True).lower()
        p = row.select_one("p")
        text = p.get_text(strip=True) if p else ""

        if "description" in header:
            description = text
        elif "job level" in header:
            job_levels = text
        elif "language" in header:
            languages = text

    # Assessment length
    length_p = soup.select_one("p:-soup-contains('Approximate Completion Time')")
    if length_p:
        m = re.search(r"(\d+)", length_p.get_text())
        if m:
            duration_minutes = int(m.group(1))

    item["description"] = description
    item["job_levels"] = [j.strip() for j in job_levels.split(",") if j.strip()] if job_levels else []
    item["languages"] = [l.strip() for l in languages.split(",") if l.strip()] if languages else []
    item["duration_minutes"] = duration_minutes
    return item


def scrape_all_list_pages(client: httpx.Client) -> list[dict]:
    """Scrape all paginated Individual Test Solutions listing pages."""
    items = []
    # type=1 = Individual Test Solutions, 12 items per page
    start = 0
    page_num = 0
    while True:
        url = f"{LIST_URL}?start={start}&type=1"
        logger.info("Scraping listing page %d: %s", page_num + 1, url)
        html = fetch_page(client, url)
        soup = BeautifulSoup(html, "lxml")

        # Find the Individual Test Solutions table
        # The page has two tables - we want the second one (Individual Test Solutions)
        tables = soup.select("table")
        its_table = None
        for table in tables:
            header = table.select_one("th.custom__table-heading__title")
            if header and "individual test" in header.get_text(strip=True).lower():
                its_table = table
                break

        if not its_table:
            # If no explicit header, try the second table
            if len(tables) >= 2:
                its_table = tables[1]
            elif tables:
                its_table = tables[0]

        if not its_table:
            logger.warning("No Individual Test Solutions table found on page %d", page_num + 1)
            break

        rows = its_table.select("tr[data-entity-id]")
        if not rows:
            break

        for row in rows:
            item = parse_list_row(row)
            if item:
                items.append(item)

        logger.info("  Found %d items on this page (total: %d)", len(rows), len(items))

        # Check for next page
        next_link = soup.select_one("a.pagination__arrow")
        # Look specifically for next page link for type=1
        pagination = soup.select("ul.pagination li a")
        has_next = False
        for a in pagination:
            href = a.get("href", "")
            if f"start={start + 12}" in href and "type=1" in href:
                has_next = True
                break

        if not has_next:
            break
        start += 12
        page_num += 1
        time.sleep(1)

    return items


def scrape_detail_pages(client: httpx.Client, items: list[dict]) -> list[dict]:
    """Scrape detail pages for each item to enrich with descriptions etc."""
    total = len(items)
    for i, item in enumerate(items):
        slug = item.get("slug", "")
        if not slug:
            logger.warning("No slug for item: %s", item["name"])
            continue
        detail_url = f"{BASE}/solutions/products/product-catalog/view/{slug}/"
        logger.info("Scraping detail %d/%d: %s", i + 1, total, item["name"])
        try:
            html = fetch_page(client, detail_url)
            parse_detail_page(html, item)
        except Exception as e:
            logger.error("Failed to scrape detail for %s: %s", item["name"], e)
            item["description"] = ""
            item["job_levels"] = []
            item["languages"] = []
            item["duration_minutes"] = None
        if (i + 1) % 20 == 0:
            time.sleep(2)
        else:
            time.sleep(0.5)
    return items


def main():
    import sys
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # If --listing-only flag, just scrape listing pages
    listing_only = "--listing-only" in sys.argv
    skip_details = "--skip-details" in sys.argv

    with httpx.Client() as client:
        logger.info("=== Scraping listing pages ===")
        items = scrape_all_list_pages(client)
        logger.info("Found %d Individual Test Solutions", len(items))

        if not listing_only and not skip_details:
            logger.info("=== Scraping detail pages ===")
            items = scrape_detail_pages(client, items)
        else:
            logger.info("Skipping detail pages (--listing-only or --skip-details flag)")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    logger.info("Catalog saved to %s (%d items)", OUT_FILE, len(items))


if __name__ == "__main__":
    main()
