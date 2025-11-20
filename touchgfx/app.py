import xml.etree.ElementTree as ET
import requests
from urllib.parse import urljoin
import csv
from datetime import datetime
import re
import time
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

# Global variable to control how many websites are fetched
MAX_URLS_TO_FETCH = 10  # Change this value as needed
FETCH_DELAY = 0.75  # Delay in seconds between requests to avoid overwhelming the server


class TouchGFXSitemapScraper:
    def __init__(self, sitemap_url: str = "https://support.touchgfx.com/sitemap.xml"):
        self.sitemap_url = sitemap_url
        self.url_pattern = re.compile(
            r'https://support\.touchgfx\.com/4\.[12].*')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def fetch_sitemap(self) -> str:
        """Fetch the sitemap XML content"""
        try:
            response = self.session.get(self.sitemap_url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching sitemap: {e}")
            raise

    def parse_sitemap(self, xml_content: str) -> List[Dict[str, str]]:
        """Parse the sitemap XML and extract URL information"""
        try:
            root = ET.fromstring(xml_content)

            # Handle XML namespace
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            urls_data = []

            for url_element in root.findall('ns:url', namespace):
                loc_element = url_element.find('ns:loc', namespace)
                changefreq_element = url_element.find(
                    'ns:changefreq', namespace)
                priority_element = url_element.find('ns:priority', namespace)
                lastmod_element = url_element.find('ns:lastmod', namespace)

                if loc_element is not None:
                    url = loc_element.text

                    # Check if URL matches our pattern
                    if url is not None and not self.url_pattern.match(url):
                        url_data = {
                            'url': url,
                            'changefreq': changefreq_element.text if changefreq_element is not None else '',
                            'priority': priority_element.text if priority_element is not None else '',
                            'lastmod': lastmod_element.text if lastmod_element is not None else ''
                        }
                        urls_data.append(url_data)

            return urls_data

        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
            raise

    def get_last_modified_from_page(self, url: str) -> Optional[str]:
        """Get last modified date from HTTP headers"""
        try:
            # Add a custom header to indicate the purpose of the request
            headers = {
                'X-Purpose': 'last-mod-check'
            }
            # Use HEAD request to get headers without downloading full content
            response = self.session.head(
                url, timeout=10, allow_redirects=True, headers=headers)

            # Try to get last-modified from headers
            last_modified = response.headers.get('Last-Modified')
            if last_modified:
                return last_modified

            # If no Last-Modified header, try Date header
            date_header = response.headers.get('Date')
            if date_header:
                return date_header

            return None

        except requests.RequestException as e:
            print(f"Error fetching headers for {url}: {e}")
            return None

    def get_last_modified_from_html(self, url):
        try:
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Check meta tags
            meta = soup.find('meta', attrs={'name': 'last-modified'})
            if meta and meta.get('content'):
                return meta['content']
            # Check for schema.org dateModified
            schema = soup.find(attrs={'itemprop': 'dateModified'})
            if schema and schema.get('content'):
                return schema['content']
            # Add more patterns as needed
        except Exception as e:
            print(f"Error fetching/parsing HTML for {url}: {e}")
        return None

    def scrape_pages(self, urls_data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Scrape pages to get last modified information"""
        # Limit the number of URLs processed based on the global variable
        urls_data = urls_data[:MAX_URLS_TO_FETCH]
        results = []

        print(f"Processing {len(urls_data)} URLs...")

        for i, url_data in enumerate(urls_data, 1):
            print(f"Processing {i}/{len(urls_data)}: {url_data['url']}")

            # Get last modified from HTTP headers
            http_last_modified = self.get_last_modified_from_page(url_data['url'])

            # Fallback: Try to get last modified from HTML if not found in headers
            http_last_modified2 = self.get_last_modified_from_html(url_data['url'])

            result = {
                'url': url_data['url'],
                'changefreq': url_data['changefreq'],
                'priority': url_data['priority'],
                'sitemap_lastmod': url_data['lastmod'],
                'http_last_modified': http_last_modified or '',
                'http_last_modified2': http_last_modified2 or ''
            }

            results.append(result)

            # Add small delay to be respectful to the server
            time.sleep(FETCH_DELAY)

        return results

    def save_to_csv(self, data: List[Dict[str, str]], filename: str = None) -> str:
        """Save data to CSV file"""
        if filename is None:
            epoch_timestamp = int(time.time())
            filename = f"/tmp/touchgfx-{epoch_timestamp}.csv" # f"touchgfx-{epoch_timestamp}.csv"

        fieldnames = ['url', 'changefreq', 'priority', 'sitemap_lastmod', 'http_last_modified', 'http_last_modified2']

        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        print(f"Data saved to {filename}")
        return filename

    def run(self) -> str:
        """Main method to run the scraper"""
        print("Starting TouchGFX sitemap scraper...")

        # Fetch and parse sitemap
        print("Fetching sitemap...")
        xml_content = self.fetch_sitemap()

        print("Parsing sitemap...")
        urls_data = self.parse_sitemap(xml_content)

        print(f"Found {len(urls_data)} URLs matching pattern")

        if not urls_data:
            print(
                "No URLs found matching the pattern 'https://support.touchgfx.com/4.[12].*'")
            return ""

        # Scrape pages for last modified info
        results = self.scrape_pages(urls_data)

        # Save to CSV
        filename = self.save_to_csv(results)

        print(f"Scraping completed. Results saved to {filename}")
        return filename


def main():
    scraper = TouchGFXSitemapScraper()
    start_time = time.time()
    try:
        filename = scraper.run()
        elapsed = time.time() - start_time
        print(f"Process completed successfully. Output file: {filename}")
        print(f"Elapsed time: {elapsed:.2f} seconds")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Error during scraping: {e}")
        print(f"Elapsed time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
