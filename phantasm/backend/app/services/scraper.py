import logging
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.schemas import JobMetadata, Platform

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> Platform:
    """Detect job platform from URL hostname."""
    if "linkedin.com" in url:
        return "linkedin"
    if "indeed.com" in url:
        return "indeed"
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    return "unknown"


async def _get_text(page, selector: str) -> str:
    """Safely extract text content from a CSS selector."""
    try:
        el = await page.query_selector(selector)
        if el:
            text = await el.inner_text()
            return text.strip()
    except Exception:
        pass
    return ""


async def scrape_job_page(url: str) -> JobMetadata:
    """
    Open a job posting URL with Playwright and extract metadata.
    Falls back gracefully when selectors don't match.
    """
    platform = detect_platform(url)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Wait a bit for JS rendering
            await page.wait_for_timeout(2000)

            title = ""
            company = ""
            posted_date: Optional[str] = None

            if platform == "linkedin":
                title = await _get_text(
                    page, ".job-details-jobs-unified-top-card__job-title"
                )
                company = await _get_text(
                    page, ".job-details-jobs-unified-top-card__company-name"
                )
                posted_date = (
                    await _get_text(page, ".jobs-unified-top-card__posted-date")
                    or None
                )

            elif platform == "indeed":
                title = await _get_text(page, "[data-jk]") or await _get_text(
                    page, "h1.jobsearch-JobInfoHeader-title"
                )
                company = await _get_text(
                    page, ".jobsearch-InlineCompanyRating-companyName"
                )
                posted_date = await _get_text(page, ".date") or None

            elif platform == "greenhouse":
                title = await _get_text(page, "h1.app-title")
                company = await _get_text(page, ".company-name")
                if not company:
                    match = re.match(r"https?://([^.]+)\.greenhouse\.io", url)
                    company = match.group(1).replace("-", " ").title() if match else ""

            elif platform == "lever":
                title = await _get_text(page, ".posting-headline h2")
                match = re.match(r"https?://jobs\.lever\.co/([^/]+)", url)
                company = match.group(1).replace("-", " ").title() if match else ""

            # Fallbacks for title
            if not title:
                title = await _get_text(page, "h1")
            if not title:
                title = await page.title()

            # Get full page text
            raw_text = ""
            try:
                raw_text = await page.inner_text("body")
                raw_text = raw_text.strip()[:8000]
            except Exception:
                pass

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

        finally:
            await browser.close()
