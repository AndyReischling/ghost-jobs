import logging
import re
from typing import Optional
from urllib.parse import quote_plus
import httpx
from app.schemas import RedFlag

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

logger = logging.getLogger(__name__)

WEIGHT_PARITY_FAIL = 25
WEIGHT_PARITY_PASS = -10

CAREERS_PATHS = ["/careers", "/jobs", "/career", "/join-us", "/open-positions"]


def _normalize_company_to_domain(company: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", company.lower())
    return f"{cleaned}.com"


def _extract_significant_words(title: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", title.lower())
    return [w for w in words if len(w) > 3]


async def _find_careers_url_via_google(company: str) -> Optional[str]:
    """
    Search Google for the company's careers page to find the real URL
    instead of guessing the domain. Returns the first plausible careers
    URL, or None if nothing found.
    """
    query = quote_plus(f'"{company}" careers jobs site')
    search_url = f"https://www.google.com/search?q={query}&num=5"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            if response.status_code != 200:
                return None

            html = response.text
            # Extract URLs from Google results
            urls = re.findall(r'href="(https?://[^"]+)"', html)

            careers_keywords = ["career", "jobs", "job", "hiring", "openings", "positions",
                                "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
                                "icims.com", "smartrecruiters.com"]
            company_lower = company.lower()

            for url in urls:
                url_lower = url.lower()
                if "google.com" in url_lower:
                    continue
                has_company = any(
                    w in url_lower for w in re.findall(r"[a-z]+", company_lower) if len(w) > 3
                )
                has_careers = any(kw in url_lower for kw in careers_keywords)
                if has_company and has_careers:
                    logger.info(f"parity_check: Google found careers URL: {url}")
                    return url

    except Exception as e:
        logger.warning(f"parity_check: Google search failed: {e}")

    return None


async def parity_check(
    company: str, job_title: str
) -> tuple[int, Optional[RedFlag]]:
    """
    Check if the job title appears on the company's careers page.
    Strategy: Google search for careers URL first, fall back to domain
    guessing, then check page content with Playwright.
    """
    if not company or not job_title:
        return 0, None

    if not HAS_PLAYWRIGHT:
        logger.warning("parity_check: Playwright not installed, skipping")
        return 0, None

    significant_words = _extract_significant_words(job_title)
    if not significant_words:
        return 0, None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                page.set_default_timeout(10000)

                careers_url = await _find_careers_url_via_google(company)
                found_page = False

                # Try Google-discovered URL first
                if careers_url:
                    try:
                        response = await page.goto(
                            careers_url, wait_until="networkidle", timeout=10000
                        )
                        if response and response.ok:
                            found_page = True
                    except Exception:
                        pass

                # Fall back to domain guessing
                if not found_page:
                    domain = _normalize_company_to_domain(company)
                    for path in CAREERS_PATHS:
                        url = f"https://www.{domain}{path}"
                        try:
                            response = await page.goto(
                                url, wait_until="networkidle", timeout=10000
                            )
                            if response and response.ok:
                                found_page = True
                                break
                        except Exception:
                            continue

                if not found_page:
                    logger.info(
                        f"parity_check: Could not reach careers page for {company}"
                    )
                    return 0, None

                page_text = await page.inner_text("body")
                page_text_lower = page_text.lower()

                matches = sum(
                    1 for word in significant_words if word in page_text_lower
                )
                match_ratio = matches / len(significant_words)

                if match_ratio >= 0.5:
                    logger.info(
                        f"parity_check: '{job_title}' FOUND on {company} careers page "
                        f"({match_ratio:.0%} word match)"
                    )
                    return WEIGHT_PARITY_PASS, None
                else:
                    logger.info(
                        f"parity_check: '{job_title}' NOT found on {company} careers page "
                        f"({match_ratio:.0%} word match)"
                    )
                    return WEIGHT_PARITY_FAIL, RedFlag(
                        type="parity",
                        message="Not found on company careers page",
                        severity="high",
                    )

            finally:
                await browser.close()

    except Exception as e:
        logger.error(f"parity_check error: {e}")
        return 0, None
