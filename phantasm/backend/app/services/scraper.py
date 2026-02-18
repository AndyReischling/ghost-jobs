"""
Job page scraper using httpx + HTML parsing.
Routes through ScrapingBee for JS-heavy sites (LinkedIn, Indeed).
Falls back to direct httpx when no API key is set.
"""

import logging
import os
import re
from typing import Optional
from html.parser import HTMLParser
import httpx
from app.schemas import JobMetadata, Platform

logger = logging.getLogger(__name__)

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1"

# Platforms that require JS rendering + premium proxies to scrape
JS_HEAVY_PLATFORMS = {"linkedin", "indeed"}


def detect_platform(url: str) -> Platform:
    if "linkedin.com" in url:
        return "linkedin"
    if "indeed.com" in url:
        return "indeed"
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    return "unknown"


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping script/style tags."""

    def __init__(self):
        super().__init__()
        self._text_parts: list[str] = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript", "svg", "head"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._text_parts.append(text)

    def get_text(self) -> str:
        return " ".join(self._text_parts)


def _extract_visible_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def _find_meta_content(html: str, properties: list[str]) -> str:
    """Extract content from <meta> tags by property or name."""
    for prop in properties:
        pattern = rf'<meta\s+(?:[^>]*?)(?:property|name)\s*=\s*["\']?{re.escape(prop)}["\']?\s+content\s*=\s*["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        pattern2 = rf'<meta\s+content\s*=\s*["\']([^"\']+)["\']\s+(?:property|name)\s*=\s*["\']?{re.escape(prop)}["\']?'
        match2 = re.search(pattern2, html, re.IGNORECASE)
        if match2:
            return match2.group(1).strip()
    return ""


def _find_tag_text(html: str, pattern: str) -> str:
    """Extract text content from a tag matching a regex pattern."""
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if match:
        inner = match.group(1)
        clean = re.sub(r"<[^>]+>", "", inner).strip()
        return clean
    return ""


async def _fetch_via_scrapingbee(
    url: str, api_key: str, platform: str
) -> str:
    """Fetch page HTML through ScrapingBee's rendering proxy."""
    params: dict[str, str] = {
        "api_key": api_key,
        "url": url,
        "render_js": "true",
    }

    if platform in JS_HEAVY_PLATFORMS:
        params["premium_proxy"] = "true"

    logger.info(f"scraper: Fetching via ScrapingBee (platform={platform}, premium={platform in JS_HEAVY_PLATFORMS})")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(SCRAPINGBEE_URL, params=params)
        response.raise_for_status()
        return response.text


async def _fetch_direct(url: str) -> str:
    """Fetch page HTML directly via httpx."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _extract_linkedin(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r'<h1[^>]*>(.*?)</h1>')
    )
    if " - " in title and "|" in title:
        parts = title.split(" - ", 1)
        title = parts[0].strip()

    company = _find_meta_content(html, ["og:description"])
    if company and " is hiring" in company.lower():
        company = company.split(" is hiring")[0].strip()
    elif company and " posted" in company.lower():
        company = company.split(" posted")[0].strip()
    else:
        company = ""

    # Try extracting from rendered DOM if ScrapingBee returned full page
    if not title:
        title = _find_tag_text(
            html,
            r'<(?:h1|div|a)[^>]*class="[^"]*job-details-jobs-unified-top-card__job-title[^"]*"[^>]*>(.*?)</(?:h1|div|a)>'
        )
    if not company:
        company = _find_tag_text(
            html,
            r'<(?:span|a|div)[^>]*class="[^"]*job-details-jobs-unified-top-card__company-name[^"]*"[^>]*>(.*?)</(?:span|a|div)>'
        )

    posted_date = None
    return title, company, posted_date


def _extract_indeed(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r'<h1[^>]*class="[^"]*[Jj]ob[Tt]itle[^"]*"[^>]*>(.*?)</h1>')
        or _find_tag_text(html, r"<h1[^>]*>(.*?)</h1>")
    )
    if " - " in title:
        title = title.split(" - ")[0].strip()

    company = _find_meta_content(html, ["og:description"])
    if company:
        parts = company.split(" - ")
        if len(parts) >= 2:
            company = parts[0].strip()
        else:
            company = ""
    else:
        company = ""

    posted_date = None
    return title, company, posted_date


def _extract_greenhouse(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_tag_text(html, r'<h1[^>]*class="[^"]*app-title[^"]*"[^>]*>(.*?)</h1>')
        or _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r"<h1[^>]*>(.*?)</h1>")
    )
    company = (
        _find_tag_text(html, r'<span[^>]*class="[^"]*company-name[^"]*"[^>]*>(.*?)</span>')
        or _find_meta_content(html, ["og:site_name"])
    )
    if not company:
        match = re.match(r"https?://([^.]+)\.greenhouse\.io", url)
        company = match.group(1).replace("-", " ").title() if match else ""

    posted_date = None
    return title, company, posted_date


def _extract_lever(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_tag_text(html, r'<h2[^>]*>(.*?)</h2>')
        or _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r"<h1[^>]*>(.*?)</h1>")
    )
    company = _find_meta_content(html, ["og:site_name"])
    if not company:
        match = re.match(r"https?://jobs\.lever\.co/([^/]+)", url)
        company = match.group(1).replace("-", " ").title() if match else ""

    posted_date = None
    return title, company, posted_date


def _extract_generic(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r"<h1[^>]*>(.*?)</h1>")
        or _find_tag_text(html, r"<title>(.*?)</title>")
    )
    company = (
        _find_meta_content(html, ["og:site_name"])
        or ""
    )
    posted_date = None
    return title, company, posted_date


async def scrape_job_page(url: str) -> JobMetadata:
    """
    Fetch a job posting URL and extract metadata from the HTML.
    Uses ScrapingBee for JS-heavy sites when API key is available,
    falls back to direct httpx otherwise.
    """
    platform = detect_platform(url)
    scrapingbee_key = os.getenv("SCRAPINGBEE_API_KEY", "")

    use_scrapingbee = (
        scrapingbee_key
        and scrapingbee_key != "your_key_here"
    )

    try:
        if use_scrapingbee:
            html = await _fetch_via_scrapingbee(url, scrapingbee_key, platform)
        else:
            if platform in JS_HEAVY_PLATFORMS:
                logger.warning(
                    f"scraper: No SCRAPINGBEE_API_KEY set — direct fetch for {platform} "
                    "will return limited data"
                )
            html = await _fetch_direct(url)
    except httpx.HTTPStatusError as e:
        logger.error(f"scraper: HTTP {e.response.status_code} fetching {url}")
        raise RuntimeError(f"Failed to fetch page (HTTP {e.response.status_code})")
    except Exception as e:
        logger.error(f"scraper: Error fetching {url}: {e}")
        raise

    extractors = {
        "linkedin": _extract_linkedin,
        "indeed": _extract_indeed,
        "greenhouse": _extract_greenhouse,
        "lever": _extract_lever,
        "unknown": _extract_generic,
    }

    extractor = extractors.get(platform, _extract_generic)
    title, company, posted_date = extractor(html, url)

    if not title:
        title, _, _ = _extract_generic(html, url)

    raw_text = _extract_visible_text(html)[:8000]

    logger.info(
        f"scraper: Extracted from {platform} — title='{title[:60]}', "
        f"company='{company}', text_length={len(raw_text)}"
    )

    return JobMetadata(
        url=url,
        title=title,
        company=company,
        postedDate=posted_date,
        rawText=raw_text,
        platform=platform,
    )
