"""AYUR-INTEL — DRAVYA Portal Web Scraper.

Scrapes comprehensive Ayurvedic medicinal plant data from the CCRAS DRAVYA portal
(https://dravya.ccras.org.in/) and saves structured information into JSON format.

Features:
- Automated discovery of all plants via pagination and direct routing
- Structured extraction:
  * Scientific Name & Author
  * Family Name
  * Vernacular Names across Indian & global languages
  * Etymology (Sanskrit synonyms, diacritics, classical etymological definitions)
  * Parts Used (English, Hindi, diacritics, classical references)
  * Rasa, Guna, Virya, Vipaka (Ayurvedic pharmacological properties)
  * Karma & Doshakarma (Actions & Dosha balance)
  * Therapeutic Usage (Indications, diseases, disorders)
  * Classical Dosage & Formulations (AFI references)
  * Pharmacopoeial Status & Classical References (API monographs)
  * Mahakashaya, Varga, Skandha taxonomical classifications
- Rate limiting (default: 1.0s delay) to respect server capacity
- Resumable scraping: skips already fetched plants if interrupted
- Robust error handling, retries with exponential backoff, and progress reporting

Usage:
    python scripts/scrape_dravya.py
    python scripts/scrape_dravya.py --output dravya_full_data.json --delay 1.0
    python scripts/scrape_dravya.py --limit 10  # Test first 10 plants
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://dravya.ccras.org.in"
DEFAULT_OUTPUT_FILE = "dravya_full_data.json"
DEFAULT_DELAY_SECONDS = 1.0
DEFAULT_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("dravya_scraper")


# ---------------------------------------------------------------------------
# HTML Parser
# ---------------------------------------------------------------------------

def clean_text(text: Optional[str]) -> str:
    """Normalize whitespace and clean text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_table_rows(container: Any) -> List[Dict[str, str]]:
    """Extract rows from an HTML table inside an accordion or section."""
    table = container.find("table")
    if not table:
        return []

    headers: List[str] = []
    thead = table.find("thead")
    if thead:
        headers = [clean_text(th.get_text()) for th in thead.find_all(["th", "td"])]
    if not headers:
        first_tr = table.find("tr")
        if first_tr:
            headers = [clean_text(th.get_text()) for th in first_tr.find_all(["th", "td"])]

    # Standardize header names
    clean_headers: List[str] = []
    for idx, h in enumerate(headers):
        normalized = re.sub(r"[^\w\s]", "", h).strip().lower().replace(" ", "_")
        clean_headers.append(normalized or f"col_{idx}")

    rows: List[Dict[str, str]] = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row_dict: Dict[str, str] = {}
        for idx, td in enumerate(tds):
            col_key = clean_headers[idx] if idx < len(clean_headers) else f"col_{idx}"
            val = clean_text(td.get_text())
            row_dict[col_key] = val
        if row_dict and any(row_dict.values()):
            rows.append(row_dict)

    return rows


def parse_plant_html(html: str, plant_id: Optional[int] = None, url: Optional[str] = None) -> Dict[str, Any]:
    """Parse complete plant profile HTML into structured dictionary."""
    soup = BeautifulSoup(html, "html.parser")

    plant_data: Dict[str, Any] = {
        "plant_id": plant_id,
        "url": url or "",
        "scientific_name": "",
        "family": "",
        "vernacular_names": {},
        "etymology": [],
        "parts_used": [],
        "guna": [],
        "virya": [],
        "vipaka": [],
        "karma": [],
        "doshakarma": [],
        "therapeutic_usage": [],
        "dosage": [],
        "dosage_formulations": [],
        "classical_references": [],
        "mahakashaya": [],
        "varga": [],
        "skandha": [],
    }

    # 1. Scientific Profile & Family
    for card in soup.find_all(class_="card"):
        card_text = card.get_text()
        if "Scientific Profile" in card_text:
            for item in card.find_all(class_=lambda x: x and "d-flex" in x):
                txt = clean_text(item.get_text(" "))
                if "Scientific Name" in txt or ("Scientific" in txt and "Name" in txt):
                    val_el = item.find(class_="font-weight-bold")
                    if val_el:
                        plant_data["scientific_name"] = clean_text(val_el.get_text())
                    else:
                        m = re.search(r"Scientific\s+Name\s+(.+)", txt, re.IGNORECASE)
                        if m:
                            plant_data["scientific_name"] = clean_text(m.group(1))
                elif "Family Name" in txt or ("Family" in txt and "Name" in txt):
                    val_el = item.find(class_="font-weight-bold")
                    if val_el:
                        plant_data["family"] = clean_text(val_el.get_text())
                    else:
                        m = re.search(r"Family\s+Name\s+(.+)", txt, re.IGNORECASE)
                        if m:
                            plant_data["family"] = clean_text(m.group(1))

    # Fallback for Scientific Name if not in card
    if not plant_data["scientific_name"]:
        page_title = clean_text(soup.title.string if soup.title else "")
        if "-" in page_title:
            plant_data["scientific_name"] = page_title.split("-")[0].strip()

    # 2. Vernacular Names
    for card in soup.find_all(class_="card"):
        if "Vernacular Names" in card.get_text():
            for block in card.find_all(class_=lambda x: x and "p-3" in x):
                badge = block.find(class_="badge")
                p = block.find("p")
                if badge and p:
                    lang = clean_text(badge.get_text())
                    names = [
                        clean_text(n)
                        for n in p.get_text().split(",")
                        if clean_text(n)
                    ]
                    if lang and names:
                        plant_data["vernacular_names"][lang] = names

    # 3. Accordion Sections
    for acc in soup.find_all(class_="accordion-item"):
        acc_head = acc.find(["h2", "h3", "h4", "button", "a"])
        head_text = clean_text(acc_head.get_text()).lower() if acc_head else ""
        parsed_rows = parse_table_rows(acc)

        if "etymology" in head_text:
            plant_data["etymology"] = parsed_rows
        elif "parts used" in head_text or "part used" in head_text:
            plant_data["parts_used"] = parsed_rows
        elif "guna" in head_text:
            plant_data["guna"] = parsed_rows
        elif "virya" in head_text:
            plant_data["virya"] = parsed_rows
        elif "vipaka" in head_text:
            plant_data["vipaka"] = parsed_rows
        elif "doshakarma" in head_text:
            plant_data["doshakarma"] = parsed_rows
        elif "karma" in head_text:
            plant_data["karma"] = parsed_rows
        elif "therapeutic" in head_text or "usage" in head_text:
            plant_data["therapeutic_usage"] = parsed_rows
        elif "dosage formulation" in head_text:
            plant_data["dosage_formulations"] = parsed_rows
        elif "dose" in head_text:
            plant_data["dosage"] = parsed_rows
        elif "pharmacopoeial" in head_text or "reference" in head_text:
            plant_data["classical_references"] = parsed_rows
        elif "mahakashaya" in head_text:
            plant_data["mahakashaya"] = parsed_rows
        elif "varga" in head_text:
            plant_data["varga"] = parsed_rows
        elif "skandha" in head_text:
            plant_data["skandha"] = parsed_rows

    return plant_data


# ---------------------------------------------------------------------------
# Scraper Engine
# ---------------------------------------------------------------------------

class DravyaScraper:
    """Scrapes CCRAS DRAVYA portal with rate limiting and session management."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        output_file: str = DEFAULT_OUTPUT_FILE,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.delay = delay_seconds
        self.output_file = output_file
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        })

    def fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with retries and exponential backoff."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    return None
                else:
                    logger.warning("HTTP %d for %s (attempt %d/%d)", response.status_code, url, attempt, MAX_RETRIES)
            except requests.RequestException as e:
                logger.warning("Request error for %s (attempt %d/%d): %s", url, attempt, MAX_RETRIES, e)

            time.sleep(self.delay * attempt)

        return None

    def discover_all_plant_urls(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Discover all plant URLs from the portal pagination and range scans."""
        logger.info("🔍 Discovering plants from %s/all_plants...", self.base_url)
        plant_catalog: Dict[int, Dict[str, Any]] = {}

        page = 1
        while True:
            page_url = f"{self.base_url}/all_plants?page={page}"
            html = self.fetch_url(page_url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            found_on_page = 0

            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/plant/" in href:
                    full_url = urljoin(self.base_url, href)
                    # Extract plant ID from URL, e.g. /plant/374/withania-somnifera or /plant/374
                    m = re.search(r"/plant/(\d+)(?:/([a-zA-Z0-9_\-]+))?", full_url)
                    if m:
                        p_id = int(m.group(1))
                        name = clean_text(a.get_text())
                        if p_id not in plant_catalog:
                            plant_catalog[p_id] = {
                                "id": p_id,
                                "url": full_url,
                                "name": name if name and name.lower() != "view" else "",
                            }
                            found_on_page += 1

            logger.info("  📄 Page %d: discovered %d new plants (Total: %d)", page, found_on_page, len(plant_catalog))

            if limit and len(plant_catalog) >= limit:
                break

            # Check if there is a next page
            has_next = False
            for a in soup.find_all("a", href=True):
                if f"?page={page + 1}" in a["href"]:
                    has_next = True
                    break

            if not has_next or page >= 60:
                break

            page += 1
            time.sleep(self.delay)

        # In addition, if no limit, check direct IDs up to 385 to ensure 100% completeness
        if not limit:
            max_known_id = max(plant_catalog.keys()) if plant_catalog else 378
            scan_target = max(385, max_known_id + 5)
            logger.info("🔍 Verifying complete index range (1 to %d)...", scan_target)

            for p_id in range(1, scan_target + 1):
                if p_id not in plant_catalog:
                    plant_catalog[p_id] = {
                        "id": p_id,
                        "url": f"{self.base_url}/plant/{p_id}",
                        "name": "",
                    }

        # Sort by plant ID
        sorted_list = sorted(plant_catalog.values(), key=lambda x: x["id"])
        logger.info("✅ Discovery complete: %d candidate plant entries to scrape.", len(sorted_list))
        return sorted_list

    def load_existing_data(self) -> Dict[int, Dict[str, Any]]:
        """Load previously saved data to support resumption."""
        if not os.path.exists(self.output_file):
            return {}

        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item.get("plant_id"): item for item in data if item.get("plant_id")}
                elif isinstance(data, dict) and "plants" in data:
                    return {item.get("plant_id"): item for item in data["plants"] if item.get("plant_id")}
        except Exception as e:
            logger.warning("Could not read existing file %s: %s", self.output_file, e)

        return {}

    def save_data(self, plants_list: List[Dict[str, Any]]) -> None:
        """Save plants data to output JSON file."""
        out_dir = os.path.dirname(os.path.abspath(self.output_file))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        payload = {
            "metadata": {
                "source": "CCRAS DRAVYA Portal (https://dravya.ccras.org.in/)",
                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_plants": len(plants_list),
            },
            "plants": plants_list,
        }

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def run(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute full scraping pipeline."""
        start_time = time.time()
        logger.info("=" * 60)
        logger.info("🌿 STARTING DRAVYA MEDICINAL PLANTS SCRAPING")
        logger.info("Target: %s", self.base_url)
        logger.info("Output: %s", self.output_file)
        logger.info("Rate Limit Delay: %.1fs", self.delay)
        if limit:
            logger.info("Plant Limit: %d", limit)
        logger.info("=" * 60)

        # 1. Load existing data for resume support
        existing_data = self.load_existing_data()
        if existing_data:
            logger.info("🔄 Found %d previously scraped plants in %s (will skip)", len(existing_data), self.output_file)

        # 2. Discover plant URLs
        catalog = self.discover_all_plant_urls(limit=limit)
        if limit:
            catalog = catalog[:limit]

        results: Dict[int, Dict[str, Any]] = dict(existing_data)
        scraped_count = 0
        skipped_count = 0
        failed_count = 0

        # 3. Scrape each plant
        total = len(catalog)
        for idx, entry in enumerate(catalog, 1):
            p_id = entry["id"]
            url = entry["url"]

            # Check if already scraped
            if p_id in results and results[p_id].get("scientific_name"):
                skipped_count += 1
                logger.info(
                    "[%d/%d] Plant ID %d already scraped (%s). Skipping.",
                    idx,
                    total,
                    p_id,
                    results[p_id].get("scientific_name"),
                )
                continue

            logger.info("[%d/%d] Fetching Plant ID %d: %s...", idx, total, p_id, url)
            html = self.fetch_url(url)
            if not html:
                failed_count += 1
                logger.warning("❌ Failed to fetch Plant ID %d from %s", p_id, url)
                continue

            try:
                parsed = parse_plant_html(html, plant_id=p_id, url=url)
                sci_name = parsed.get("scientific_name") or f"Plant #{p_id}"
                family = parsed.get("family") or "Unknown"

                # Check if page was a real plant entry
                if not parsed.get("scientific_name") and not parsed.get("etymology") and not parsed.get("guna"):
                    logger.info("  ⚠️ Plant ID %d has no plant content (404/Empty).", p_id)
                    continue

                results[p_id] = parsed
                scraped_count += 1

                logger.info(
                    "  ✅ [%d/%d] ID %d: %s (Family: %s) | Guna: %d, Virya: %d, Karma: %d, Uses: %d",
                    idx,
                    total,
                    p_id,
                    sci_name,
                    family,
                    len(parsed.get("guna", [])),
                    len(parsed.get("virya", [])),
                    len(parsed.get("karma", [])),
                    len(parsed.get("therapeutic_usage", [])),
                )

                # Periodic save every 5 plants
                if scraped_count % 5 == 0:
                    sorted_plants = sorted(results.values(), key=lambda x: x.get("plant_id", 0))
                    self.save_data(sorted_plants)

            except Exception as e:
                failed_count += 1
                logger.error("❌ Error parsing plant ID %d: %s", p_id, e, exc_info=True)

            # Respect rate limit delay
            time.sleep(self.delay)

        # 4. Final Save
        final_list = sorted(results.values(), key=lambda x: x.get("plant_id", 0))
        self.save_data(final_list)

        elapsed = time.time() - start_time
        logger.info("=" * 60)
        logger.info("🎉 SCRAPING COMPLETE")
        logger.info("Total plants saved: %d", len(final_list))
        logger.info("Newly scraped: %d | Skipped: %d | Failed/Empty: %d", scraped_count, skipped_count, failed_count)
        logger.info("Elapsed Time: %.2f seconds", elapsed)
        logger.info("Saved to: %s", os.path.abspath(self.output_file))
        logger.info("=" * 60)

        return final_list


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Ayurvedic medicinal plant data from CCRAS DRAVYA portal into JSON."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output JSON file path (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay between requests in seconds for rate limiting (default: {DEFAULT_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Limit number of plants to scrape (useful for testing)",
    )
    args = parser.parse_args()

    scraper = DravyaScraper(
        output_file=args.output,
        delay_seconds=args.delay,
    )
    scraper.run(limit=args.limit)


if __name__ == "__main__":
    main()
