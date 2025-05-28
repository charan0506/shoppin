WebCrawler Documentation
This document provides a detailed explanation of the WebCrawler class, its methods, control flow, and how it achieves scalability and performance.

Overview
The WebCrawler class is an asynchronous web crawler designed to crawl multiple domains, extract product-related URLs, and save the results to domain-specific files. It uses Python's asyncio and aiohttp libraries for non-blocking I/O operations, making it scalable and efficient.

Scalability and Performance
1. Asynchronous Design
Uses asyncio and aiohttp for non-blocking I/O operations.
Allows multiple requests to be sent and processed concurrently.
2. Concurrency Control
Workers: Multiple worker tasks process URLs from the queue in parallel.
Semaphore: Limits the number of concurrent requests to avoid overwhelming the server.
3. Domain Isolation
Each domain is processed independently, ensuring no overlap in results.
Results are saved in separate files for better organization.
4. Efficient Resource Utilization
Avoids blocking operations by using asynchronous methods.
Respects crawl delays and rate limits to prevent server overload.
5. Scalability
Can handle multiple domains simultaneously using asyncio.gather.
Easily configurable for different numbers of workers and concurrent requests.

How It Works

Initialization:

The crawler is initialized with a list of domains and configuration parameters.

Domain Processing:

Each domain is processed independently:
Fetches robots.txt and sitemaps.
Queues initial URLs for crawling.

URL Processing:

Workers process URLs concurrently:
Fetch the URL content.
Extract product-related URLs or links for further crawling.

Parallel Execution:

Multiple domains are processed in parallel using asyncio.gather.
Result Saving:

Results for each domain are saved in separate files.

Control Flow

Initialization:

The WebCrawler class is initialized with a list of domains and optional parameters like the number of workers and concurrent requests.
It sets up necessary data structures like queues, locks, and semaphores.

Crawling Process:

The crawl method starts the crawling process:
Initializes an aiohttp.ClientSession with custom headers.
Spawns worker tasks to process URLs concurrently.
Processes each domain by fetching its robots.txt, parsing sitemaps, and queuing initial URLs.
Waits for the queue to empty and stops the workers.


Domain Processing:

Each domain is processed independently:
Fetches and parses robots.txt to respect crawling rules.
Parses sitemaps to discover additional URLs.
Queues the homepage and sitemap URLs for crawling.

URL Processing:

Each URL is processed by a worker:
Checks if the URL is allowed by robots.txt.
Skips static resources (e.g., images, CSS).
Fetches the URL content and extracts product-related URLs or links for further crawling.

Parallel Domain Crawling:

Multiple domains are processed in parallel using asyncio.gather.
Results for each domain are saved in separate files.

Class and Method Descriptions
1. __init__ Method
Purpose: Initializes the crawler with the given domains and configuration.
Parameters:
domains: List of domains to crawl.
max_workers: Number of concurrent workers (default: 10).
Key Attributes:
self.queue: An asyncio.Queue to manage URLs to be processed.
self.visited_urls: A set to track already visited URLs.
self.request_semaphore: Limits the number of concurrent requests.
self.headers: Custom HTTP headers to mimic a browser.
2. is_static_resource Method
Purpose: Checks if a URL points to a static resource (e.g., images, CSS, JS).
Returns: True if the URL is a static resource, otherwise False.
3. fetch_robots_txt Method
Purpose: Fetches and parses the robots.txt file for a domain.
Key Features:
Respects crawling rules (e.g., disallowed paths, crawl delays).
Extracts sitemap URLs if specified in robots.txt.
4. is_allowed Method
Purpose: Checks if a URL is allowed to be crawled based on robots.txt.
Returns: True if allowed, otherwise False.
5. get_crawl_delay Method
Purpose: Retrieves the crawl delay specified in robots.txt.
Returns: The crawl delay in seconds (default: 1 second).
6. parse_sitemap Method
Purpose: Fetches and parses sitemaps for a domain.
Key Features:
Handles both robots.txt-specified and default sitemap locations.
Extracts URLs from sitemaps.
7. parse_sitemap_xml Method
Purpose: Parses XML sitemaps to extract URLs.
Key Features:
Handles nested sitemaps.
Ensures unique URLs.
8. parse_nested_sitemap Method
Purpose: Processes nested sitemaps, including .gz compressed sitemaps.
9. is_product_url Method
Purpose: Checks if a URL matches product-related patterns.
Returns: True if the URL is a product URL, otherwise False.
10. extract_links Method
Purpose: Extracts all valid links from an HTML page.
Key Features:
Resolves relative links to absolute URLs.
Extracts links from <a>, <link>, and <meta> tags.
11. has_product_schema Method
Purpose: Checks if a page contains product schema in JSON-LD format.
Returns: True if product schema is found, otherwise False.
12. process_url Method
Purpose: Processes a single URL.
Key Features:
Skips static resources and already visited URLs.
Respects robots.txt rules and crawl delays.
Fetches the URL content and extracts product-related URLs or links.
13. worker Method
Purpose: A worker task that continuously processes URLs from the queue.
Key Features:
Handles errors gracefully.
Marks URLs as completed after processing.
14. crawl_domain Method
Purpose: Handles crawling for a single domain.
Key Features:
Fetches robots.txt and sitemaps.
Queues initial URLs (homepage and sitemap URLs).
15. crawl Method
Purpose: The main entry point for the crawling process.
Key Features:
Spawns workers to process URLs concurrently.
Waits for the queue to empty before stopping workers.
16. process_all_domains and crawl_and_save Functions
Purpose: Handles parallel processing of multiple domains.
Key Features:
Creates a separate WebCrawler instance for each domain.
Saves results to domain-specific files.

Conclusion
The WebCrawler class is a scalable and efficient solution for crawling multiple domains. Its asynchronous design, concurrency control, and domain isolation make it suitable for large-scale web crawling tasks. By respecting server rules and optimizing resource usage, it achieves a balance between performance and server friendliness.
