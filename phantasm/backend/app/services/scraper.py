"""
Job page scraper using httpx + HTML parsing.
Works on serverless (no Playwright required).
"""

import logging
import re
from typing import Optional
from html.parser import HTMLParser
import httpx
from app.schemas import JobMetadata, Platform

logger = logging.getLogger(__name__)


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
        # og:title, og:site_name, etc.
        pattern = rf'<meta\s+(?:[^>]*?)(?:property|name)\s*=\s*["\']?{re.escape(prop)}["\']?\s+content\s*=\s*["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Content before property (some sites flip the order)
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


def _extract_linkedin(html: str, url: str) -> tuple[str, str, Optional[str]]:
    title = (
        _find_meta_content(html, ["og:title"])
        or _find_tag_text(html, r'<h1[^>]*>(.*?)</h1>')
    )
    # og:title on LinkedIn is often "Job Title - Company | LinkedIn"
    if " - " in title and "|" in title:
        parts = title.split(" - ", 1)
        title = parts[0].strip()

    company = _find_meta_content(html, ["og:description"])
    # og:description often starts with company name
    if company and " is hiring" in company.lower():
        company = company.split(" is hiring")[0].strip()
    elif company and " posted" in company.lower():
        company = company.split(" posted")[0].strip()
    else:
        company = ""

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
    Fetch a job posting URL via HTTP and extract metadata from the HTML.
    Works on serverless — no browser required.
    """
    platform = detect_platform(url)

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
        html = response.text

    extractors = {
        "linkedin": _extract_linkedin,
        "indeed": _extract_indeed,
        "greenhouse": _extract_greenhouse,
        "lever": _extract_lever,
        "unknown": _extract_generic,
    }

    extractor = extractors.get(platform, _extract_generic)
    title, company, posted_date = extractor(html, url)

    # Fallback to generic extraction
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
