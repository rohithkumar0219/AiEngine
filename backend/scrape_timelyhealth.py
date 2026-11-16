"""
TimelyHealth Scraper - Targeted scraper for timelyhealth.in
Scrapes the employee list page and stores real data for Payroll AI agent.
"""
import sys, os, json, time, pathlib, hashlib
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from markdownify import markdownify as md

ROOT = pathlib.Path(__file__).parent.resolve()
PAGES_FILE  = ROOT / "data" / "raw"       / "iryax_pages.json"
CHUNKS_FILE = ROOT / "data" / "processed" / "iryax_chunks.json"
TH_RAW_FILE = ROOT / "data" / "raw"       / "timelyhealth_data.json"

TARGETS = [
    "https://www.timelyhealth.in/employeelist",
    "https://www.timelyhealth.in",
    "https://www.timelyhealth.in/employee-login",
]

def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    main = soup.find("main") or soup.find("body") or soup
    return md(str(main), heading_style="ATX", bullets="-").strip()

def scrape_url(page, url: str) -> dict:
    print(f"  → Scraping: {url}")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(3)  # extra wait for dynamic data
        html = page.content()
        title = page.title()
        markdown = html_to_markdown(html)
        soup = BeautifulSoup(html, "html.parser")

        # Extract table data if present (employee list)
        tables = []
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            rows = []
            for tr in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            tables.append({"headers": headers, "rows": rows})

        # Extract all visible text cards/list items
        cards = []
        for el in soup.select(".card, .employee-card, .list-item, [class*='employee'], [class*='staff'], li"):
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 10:
                cards.append(text[:300])

        return {
            "url": url,
            "title": title,
            "markdown": markdown,
            "tables": tables,
            "cards": cards[:50],  # limit to 50 cards
            "html_length": len(html),
        }
    except PlaywrightTimeoutError:
        print(f"  ✗ Timeout on {url}")
        return {"url": url, "title": "", "markdown": "", "tables": [], "cards": [], "html_length": 0}
    except Exception as e:
        print(f"  ✗ Error on {url}: {e}")
        return {"url": url, "title": "", "markdown": "", "tables": [], "cards": [], "html_length": 0}

def make_chunk_id(url: str, content: str) -> str:
    raw = f"{url}::{content[:200]}"
    return "chunk_" + hashlib.md5(raw.encode()).hexdigest()[:12]

def run():
    print("=== TimelyHealth Scraper ===")
    print("Target: timelyhealth.in/employeelist + related pages\n")

    scraped_data = {}
    new_chunks = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for url in TARGETS:
            result = scrape_url(page, url)
            scraped_data[url] = result
            mkd = result.get("markdown", "")
            if mkd:
                # Split into chunks of ~1400 chars
                paragraphs = mkd.split("\n\n")
                current = ""
                for p in paragraphs:
                    if len(current) + len(p) < 1400:
                        current += p + "\n\n"
                    else:
                        if current.strip():
                            cid = make_chunk_id(url, current)
                            new_chunks.append({"chunk_id": cid, "content": current.strip(), "url": url, "label": f"TimelyHealth: {result['title']}"})
                        current = p + "\n\n"
                if current.strip():
                    cid = make_chunk_id(url, current)
                    new_chunks.append({"chunk_id": cid, "content": current.strip(), "url": url, "label": f"TimelyHealth: {result['title']}"})

            tables = result.get("tables", [])
            for t in tables:
                if t.get("rows"):
                    table_text = "Employees table:\n"
                    if t.get("headers"):
                        table_text += " | ".join(t["headers"]) + "\n"
                    for row in t["rows"]:
                        table_text += " | ".join(row) + "\n"
                    cid = make_chunk_id(url, table_text)
                    new_chunks.append({"chunk_id": cid, "content": table_text.strip(), "url": url, "label": f"TimelyHealth Employee Data"})

        browser.close()

    # Save raw timelyhealth data
    TH_RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
    TH_RAW_FILE.write_text(json.dumps(scraped_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Raw data saved → {TH_RAW_FILE}")

    # Merge into iryax_pages.json
    if PAGES_FILE.exists():
        pages = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
    else:
        pages = {}
    for url, data in scraped_data.items():
        pages[url] = data.get("markdown", "")
    PAGES_FILE.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Updated iryax_pages.json ({len(pages)} pages total)")

    # Merge into iryax_chunks.json (remove old timelyhealth chunks, add new)
    if CHUNKS_FILE.exists():
        chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    else:
        chunks = []
    chunks = [c for c in chunks if "timelyhealth" not in c.get("url", "")]
    chunks.extend(new_chunks)
    CHUNKS_FILE.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Updated iryax_chunks.json ({len(chunks)} total chunks, +{len(new_chunks)} from timelyhealth)")

    # Print summary
    print("\n=== Scrape Summary ===")
    for url, data in scraped_data.items():
        tables = data.get("tables", [])
        total_rows = sum(len(t.get("rows", [])) for t in tables)
        cards = len(data.get("cards", []))
        print(f"  {url}")
        print(f"    Title: {data.get('title', 'N/A')}")
        print(f"    Markdown length: {len(data.get('markdown', ''))} chars")
        print(f"    Tables: {len(tables)} ({total_rows} rows)")
        print(f"    Cards/list items: {cards}")

    print(f"\nTotal new chunks added: {len(new_chunks)}")

    # Print first table sample if found
    for url, data in scraped_data.items():
        for t in data.get("tables", []):
            if t.get("rows"):
                print(f"\n=== Employee Table from {url} ===")
                if t.get("headers"):
                    print("Headers:", t["headers"])
                for row in t["rows"][:10]:
                    print("Row:", row)
                break

if __name__ == "__main__":
    run()

