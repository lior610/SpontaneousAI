from playwright.sync_api import sync_playwright
from main import GooglePlace
from selectolax.parser import HTMLParser
import pandas as pd
from typing import List
import time

# CONSTANTS
CATEGORIES = ("Restaurant", "Cafe", "Museum", "Park", "Tourist Attractions", "Historic Sites", "ATM", "Pharmacy")
GOOGLE_MAPS_URL = "https://www.google.com/maps"

# --- Functions ---
def parse_places_from_html(html_content: str) -> List[GooglePlace]:
    # Placeholder for actual HTML parsing logic
    # This function should parse the HTML content and extract place details
    print("Parsing data...")
    tree = HTMLParser(html_content)
    
    results = []
    # Find all divs that look like a result card
    # A safer bet is looking for 'div[role="article"]' but Selectolax needs CSS selectors.
    
    for node in tree.css('div[role="article"]'):
        try:
            # We use 'aria-label' usually found on the anchor tag or main div
            name = node.attributes.get('aria-label')
            
            # If aria-label is empty, try to find the h1-equivalent text
            if not name:
                name_node = node.css_first("div.fontHeadlineSmall") # Common class for title
                name = name_node.text() if name_node else "Unknown"

            # Extract Rating
            rating_node = node.css_first("span.fontBodyMedium > span")
            rating = rating_node.text() if rating_node else "N/A"
            
            if name:
                results.append({"name": name, "rating": rating})
        except Exception as e:
            continue
    
    print(results)
    print(f"Extracted {len(results)} places.")
    return []


def get_html_by_category(category: str, city_name: str) -> str:
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="en-US", extra_http_headers={"Accept-Language": "en-US"})
        page = context.new_page()
        page.goto(GOOGLE_MAPS_URL + "?hl=en")

        # 1. Type search query
        page.wait_for_selector("input#searchboxinput")
        page.fill("input#searchboxinput", f"{category} in {city_name}")
        page.keyboard.press("Enter")
        page.wait_for_selector('div[role="feed"]', timeout=10000)
        
        # 2. Optimized Scrolling (Load all data first)
        print("Scrolling to load data...")
        sidebar = page.locator('div[role="feed"]')
        
        for i in range(20): 
            # Scroll to bottom of the sidebar container
            sidebar.evaluate("node => node.scrollTop = node.scrollHeight")
            time.sleep(1.5) # Wait for network to fetch new batch
            print(f"Scroll batch {i+1}/20")
        
        # 3. Extract HTML to memory
        print("Extracting HTML...")
        html_content = sidebar.inner_html()
        
        browser.close()
        return html_content

def debug_one_place(html):
    tree = HTMLParser(html)
    node = tree.css_first('div[role="article"]')
    print(node.attributes)
    input("press enter")
    print(node.html)
    # for node in tree.css('div[role="article"]'):

# html = get_html_by_category("Restaurant", "New York")
with open("debug.html", "r", encoding="utf-8") as f:
    html = f.read()
places = debug_one_place(html)