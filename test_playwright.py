import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
from src.scrapers.playwright_helper import get_page_source_playwright


def test():
    urls = [
        "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/canberra-resident-applicant-eligibility",
        "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria/overseas-applicant-eligibility",
        "https://www.act.gov.au/migration/skilled-migrants/190-nomination-criteria",
    ]
    for url in urls:
        print(f"Testing {url}")
        html = get_page_source_playwright(
            url, wait_for_selector=".col-md-8", extra_wait_seconds=1, bypass_cf=True
        )
        if html:
            soup = BeautifulSoup(html, "html.parser")
            el = soup.select_one(".col-md-8")
            if el:
                txt = el.get_text(separator="\n", strip=True)
                print(f"Found .col-md-8, length: {len(txt)}")
                print(txt[:200])
            else:
                print("No .col-md-8 found")
        else:
            print("Failed to get HTML")


if __name__ == "__main__":
    test()
