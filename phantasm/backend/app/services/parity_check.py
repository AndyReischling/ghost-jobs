import logging
import re
from typing import Optional
from playwright.async_api import async_playwright
from app.schemas import RedFlag

logger = logging.getLogger(__name__)

WEIGHT_PARITY_FAIL = 25
WEIGHT_PARITY_PASS = -10

# Common careers page path patterns
CAREERS_PATHS = ["/careers", "/jobs", "/career", "/join-us", "/open-positions"]


def _normalize_company_to_domain(company: str) -> str:
    """
    Best-effort conversion of company name to a domain.
    E.g. 'Acme Corp' → 'acmecorp.com'
    """
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", company.lower())
    return f"{cleaned}.com"


def _extract_significant_words(title: str) -> list[str]:
    """Extract words longer than 3 characters for fuzzy matching."""
    words = re.findall(r"[a-zA-Z]+", title.lower())
    return [w for w in words if len(w) > 3]


async def parity_check(
    company: str, job_title: str
) -> tuple[int, Optional[RedFlag]]:
    """
    Use Playwright to check if the job title appears on the company's
    careers page. Returns a (score_delta, optional_flag) tuple.
    """
    if not company or not job_title:
        return 0, None

    domain = _normalize_company_to_domain(company)
    significant_words = _extract_significant_words(job_title)

    if not significant_words:
        return 0, None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                page.set_default_timeout(10000)

                for path in CAREERS_PATHS:
                    url = f"https://www.{domain}{path}"
                    try:
                        response = await page.goto(
                            url, wait_until="networkidle", timeout=10000
                        )
                        if response and response.ok:
                            break
                    except Exception:
                        continue
                else:
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
