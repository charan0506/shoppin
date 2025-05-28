import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import re
import json
from tldextract import extract
import gzip
from io import BytesIO
import time

class WebCrawler:
    def __init__(self, domains, max_workers=10):
        print(f"🚀 Initializing WebCrawler for domains: {domains}")
        self.domains = domains
        self.product_urls = []
        self.visited_urls = set()
        self.robot_parsers = {}
        self.headers = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7","accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "dnt": "1",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}
        self.product_patterns = [
            re.compile(r'/product/'),
            re.compile(r'/products/'),
            re.compile(r'/p/'),
            re.compile(r'\b(?:id|sku|product_id)=[0-9]+', re.I),
            re.compile(r'/item/'),
            re.compile(r'/p-[a-zA-Z0-9]+'),
        ]
        self.queue = asyncio.Queue()
        self.visited_lock = asyncio.Lock()
        self.domain_locks = {}
        self.last_request_time = {}
        self.max_workers = max_workers
        self.session = None
        self.request_semaphore = asyncio.Semaphore(5)
        print("✅ Crawler initialization complete\n")

    def is_static_resource(self, url):
        static_ext = (
            '.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.svg',
            '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.zip', '.gz',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.webp',
            '.avi', '.mov', '.mkv', '.rar', '.7z', '.tar', '.bz2', '.mpg', '.mpeg'
        )
        return url.split('?')[0].lower().endswith(static_ext)

    async def fetch_robots_txt(self, domain):
        print(f"\n🔍 Checking robots.txt for {domain}")
        parser = None
        urls = [f'https://{domain}/robots.txt']
        
        for robots_url in urls:
            try:
                print(f"⏳ Attempting to fetch {robots_url}")
                async with self.session.get(robots_url, allow_redirects=True, ssl=False) as response:
                    if response.status == 200:
                        print(f"✅ Found robots.txt at {robots_url}")
                        content = await response.text()
                        parser = RobotFileParser()
                        parser.parse(content.splitlines())
                        print(f"📋 Parsed {len(content.splitlines())} rules from robots.txt")
                        if parser.site_maps():
                            print(f"🗺 Found {len(parser.site_maps())} sitemaps in robots.txt")
                        break
            except Exception as e:
                print(f"⚠️ Error fetching {robots_url}: {str(e)[:50]}")
        
        self.robot_parsers[domain] = parser
        return parser

    def is_allowed(self, url, domain):
        parser = self.robot_parsers.get(domain)
        if parser:
            return parser.can_fetch(self.headers['User-Agent'], url)
        return True

    def get_crawl_delay(self, domain):
        parser = self.robot_parsers.get(domain)
        if parser:
            return parser.crawl_delay(self.headers['User-Agent']) or 1
        return 1

    async def parse_sitemap(self, domain):
        print(f"\n🗺 Processing sitemaps for {domain}")
        parser = self.robot_parsers.get(domain)
        sitemap_urls = []
        
        if parser and parser.site_maps():
            sitemap_urls = parser.site_maps()
            print(f"🔗 Found {len(sitemap_urls)} sitemap(s) in robots.txt")
        else:
            sitemap_urls = [f'https://{domain}/sitemap.xml']
            print("⚠️ No sitemaps found in robots.txt, using default locations")
        
        found_urls = []
        for sitemap_url in sitemap_urls:
            try:
                print(f"⏳ Fetching sitemap: {sitemap_url}")
                async with self.session.get(sitemap_url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '')
                        if 'xml' in content_type or sitemap_url.endswith('.xml'):
                            text = await response.text()
                            new_urls = await self.parse_sitemap_xml(text, sitemap_url)
                            print(f"📄 Processed sitemap {sitemap_url}, found {len(new_urls)} URLs")
                            found_urls.extend(new_urls)
            except Exception as e:
                print(f"⚠️ Error processing sitemap {sitemap_url}: {str(e)[:50]}")
        return found_urls

    async def parse_sitemap_xml(self, xml_content, base_url):
        print(f"📄 Parsing sitemap XML from: {base_url}")
        soup = await asyncio.to_thread(BeautifulSoup, xml_content, 'xml')
        urls = []
        if soup.find('sitemapindex'):
            print(f"🔍 Found sitemap index in: {base_url}")
            for sitemap in soup.find_all('sitemap'):
                loc = sitemap.find('loc')
                if loc:
                    nested_url = loc.text.strip()
                    print(f"➡️ Found nested sitemap URL: {nested_url}")
                    urls.extend(await self.parse_nested_sitemap(nested_url))
        else:
            print(f"🔗 Found URLs in sitemap: {base_url}")
            for loc in soup.find_all('loc'):
                if loc:
                    urls.append(loc.text.strip())
        urls = list(set(urls))
        print(f"✅ Parsed {len(urls)} unique URLs from sitemap")
        return urls

    async def parse_nested_sitemap(self, sitemap_url):
        print(f"📄 Parsing nested sitemap: {sitemap_url}")
        try:
            async with self.session.get(sitemap_url) as response:
                if response.status == 200:
                    if sitemap_url.endswith('.gz'):
                        print(f"📦 Decompressing gzipped sitemap: {sitemap_url}")
                        data = await response.read()
                        decompressed = await asyncio.to_thread(gzip.decompress, data)
                        soup = await asyncio.to_thread(BeautifulSoup, decompressed, 'xml')
                    else:
                        print(f"📄 Fetching and parsing XML sitemap: {sitemap_url}")
                        text = await response.text()
                        soup = await asyncio.to_thread(BeautifulSoup, text, 'xml')
                    
                    urls_nested = [loc.text.strip() for loc in soup.find_all('loc') if loc]
                    print(f"✅ Found {len(urls_nested)} URLs in nested sitemap: {sitemap_url}")
                    return urls_nested
                
        except Exception as e:
            print(f"⚠️ Error parsing nested sitemap {sitemap_url}: {str(e)[:50]}")
        return []

    def is_product_url(self, url):
        return any(pattern.search(url) for pattern in self.product_patterns)

    def extract_links(self, html, base_url):
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for tag in soup.find_all(['a', 'link'], href=True):
            full_url = urljoin(base_url, tag['href'])
            parsed = urlparse(full_url)
            normalized = parsed._replace(fragment='', query='').geturl()
            links.add(normalized)
        for tag in soup.find_all('meta', {'content': True, 'property': re.compile(r'og:url', re.I)}):
            full_url = urljoin(base_url, tag['content'])
            links.add(full_url)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Product' and data.get('url'):
                    links.add(urljoin(base_url, data['url']))
            except json.JSONDecodeError:
                pass
        return list(links)

    def has_product_schema(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script', {'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get('@type') == 'Product':
                            return True
                elif data.get('@type') == 'Product':
                    return True
            except json.JSONDecodeError:
                continue
        return False

    async def process_url(self, url):
        if len(self.product_urls) >= 100:
            self.product_urls = list(set(self.product_urls))  # Ensure uniqueness
            print("⚠️ Product limit reached. Stopping further processing.")
            return
    
        if self.is_static_resource(url):
                print(f"🖼 Skipping static resource: {url}")
                return
        domain = urlparse(url).netloc
        print(f"🔗 Extracted domain: {domain} starting_domain { self.domains[0]}")
        print(f"\n🌐 Processing URL: {url}")


        async with self.domain_locks.setdefault(domain, asyncio.Lock()):
            last_request = self.last_request_time.get(domain, 0)
            delay = self.get_crawl_delay(domain)
            if time.time() - last_request < delay:
                wait_time = delay - (time.time() - last_request)
                print(f"⏳ Respecting crawl delay of {delay}s for {domain}, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
            self.last_request_time[domain] = time.time()
        

        if extract(domain).registered_domain not in self.domains[0]:
            print(f"🚫 Skipping URL outside the domain: {url}")
            return
        
        async with self.visited_lock:
            if url in self.visited_urls:
                print(f"⏭ Already visited: {url}")
                return
            self.visited_urls.add(url)
            print(f"📥 Added to visited: {url} (Total: {len(self.visited_urls)})")

        if not self.is_allowed(url, domain):
            print(f"🚫 Blocked by robots.txt: {url}")
            return

        async with self.request_semaphore:
            try:
                #await asyncio.sleep(1)
                print(f"📡 Fetching: {url}")
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    print(f"⚡ Response: {url} - Status {response.status}")
                    
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '').lower()
                        
                        if 'xml' in content_type:
                            text = await response.text()
                            new_urls = await self.parse_sitemap_xml(text, url)
                            print(f"🔍 Found {len(new_urls)} URLs in sitemap")
                            for new_url in new_urls:
                                await self.queue.put(new_url)
                            return
                            
                        if 'html' not in content_type:
                            print(f"📄 Non-HTML content: {content_type}")
                            return
                            
                        html = await response.text()
                        
                        if await asyncio.to_thread(self.is_product_url, url):
                            print(f"🛍 Product URL detected: {url}")
                            self.product_urls.append(url)
                            
                        if await asyncio.to_thread(self.has_product_schema, html):
                            print(f"📦 Product schema detected: {url}")
                            self.product_urls.append(url)
                            
                        links = await asyncio.to_thread(self.extract_links, html, url)
                        print(f"🔗 Found {len(links)} links on page")
                        
                        for link in links:
                            parsed = urlparse(link)
                            if extract(parsed.netloc).registered_domain == extract(domain).registered_domain:
                                await self.queue.put(link)
                        # Add a fixed delay of 0.5 seconds
                
                                
            except Exception as e:
                print(f"⚠️ Error processing {url}: {str(e)[:50]}")

    async def worker(self):
        worker_id = id(asyncio.current_task())
        print(f"👷 Worker {worker_id} started")
        try:
            while True:
                url = await self.queue.get()
                print(f"🔗 Worker {worker_id} processing: {url}")
                try:
                    await self.process_url(url)
                finally:
                    self.queue.task_done()
                    print(f"✅ Worker {worker_id} completed: {url}")
        except asyncio.CancelledError:
            print(f"🛑 Worker {worker_id} shutting down")

    async def crawl_domain(self, domain):
        print(f"\n🚀 Starting crawl for domain: {domain}")
        await self.fetch_robots_txt(domain)
        
        if not self.is_allowed(f'http://{domain}/', domain):
            print(f"⛔ Domain {domain} blocked by robots.txt")
            return
            
        sitemap_urls = await self.parse_sitemap(domain)
        initial_urls = [f'http://{domain}/', f'https://{domain}/'] + sitemap_urls
        print(f"📥 Queueing {len(initial_urls)} initial URLs for {domain}")
        
        for url in initial_urls:
            await self.queue.put(url)

    async def crawl(self):
        print("\n🏁 Starting crawl process")
        self.session = aiohttp.ClientSession(headers=self.headers)
        print(f"👷 Spawning {self.max_workers} workers")
        workers = [asyncio.create_task(self.worker()) for _ in range(self.max_workers)]
        
        print(f"🌐 Beginning domain processing for {len(self.domains)} domains")
        domain_tasks = [self.crawl_domain(domain) for domain in self.domains]
        await asyncio.gather(*domain_tasks)

        while not self.queue.empty():
            print(f"⏳ Queue size: {self.queue.qsize()}")  # Monitor queue size
            await asyncio.sleep(5) 
         
        print("\n⏳ Waiting for queue to empty...")
        await self.queue.join()
        
        print("\n🛑 Stopping workers")
        for worker in workers:
            worker.cancel()
        await self.session.close()
        print(f"\n✅ Crawl complete. Found {len(self.product_urls)} product URLs")
        return self.product_urls

if __name__ == '__main__':
    domains = ['www.virgio.com', 'www.tatacliq.com', 'nykaafashion.com', 'www.westside.com']  # Add your domains here
    print("🕸 Starting web crawler")

    async def process_all_domains(domains):
        tasks = []
        for domain in domains:
            print(f"\n🌐 Preparing to process domain: {domain}")
            crawler = WebCrawler([domain])  # Create a new crawler for each domain
            tasks.append(crawl_and_save(crawler, domain))
        
        # Run all crawlers in parallel
        await asyncio.gather(*tasks)

    async def crawl_and_save(crawler, domain):
        product_urls = await crawler.crawl()
        output_file = f"{domain.replace('.', '_')}_urls.txt"  # Replace dots with underscores for the filename
        print(f"\n💾 Saving results to {output_file}")
        with open(output_file, 'w') as f:
            for url in product_urls:
                f.write(f"{url}\n")
        print(f"✅ Results saved successfully for {domain}")

    # Run the async function to process all domains
    asyncio.run(process_all_domains(domains))