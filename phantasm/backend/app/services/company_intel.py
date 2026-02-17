"""
Company intelligence and legitimacy analysis.
Uses web search, Wikipedia, and domain analysis to assess whether a company
is a real, stable employer or a red-flag entity.
"""

import logging
import os
import re
from typing import Optional
import httpx
from app.schemas import RedFlag

logger = logging.getLogger(__name__)

# --- Tunable weights ---
WEIGHT_NO_WEB_PRESENCE = 15
WEIGHT_VERY_NEW_COMPANY = 8
WEIGHT_STAFFING_AGENCY = 12
WEIGHT_CONTROVERSIAL_MODEL = 10
WEIGHT_TINY_COMPANY_BIG_HIRE = 8
WEIGHT_HIGH_TURNOVER_SIGNALS = 10

# Staffing / temp agencies and outsourcing firms (common ghost job factories)
STAFFING_KEYWORDS = [
    "staffing", "recruiting", "recruitment", "talent acquisition",
    "temp agency", "temporary staffing", "contract staffing",
    "manpower", "outsourcing", "consulting firm",
    "placement agency", "employment agency", "headhunter",
    "body shop", "contracting", "staff augmentation",
]

# Business models that rely heavily on freelance / disposable labor
FREELANCE_RELIANCE_KEYWORDS = [
    "freelance", "1099", "independent contractor", "gig",
    "per diem", "on-call", "as-needed basis", "project-based",
    "no benefits", "no health insurance", "unpaid internship",
]

# Signals of high turnover / bad workplace
TURNOVER_SIGNALS = [
    "high growth", "rapidly scaling", "constant change",
    "high-pressure", "must be available 24/7", "on call",
    "unlimited pto",  # often means no PTO tracking = guilt culture
    "startup mentality",
    "we work hard and play hard",
    "we're like a family",
    "hustle",
    "grind",
]

# Known large staffing/outsourcing companies
KNOWN_STAFFING_FIRMS = [
    "robert half", "adecco", "randstad", "manpower", "kelly services",
    "hays", "michael page", "kforce", "insight global", "tek systems",
    "teksystems", "aerotek", "modis", "apex systems", "cybercoders",
    "dice", "toptal", "upwork", "fiverr", "belay", "boldly",
    "staffmark", "spherion", "express employment", "jobot",
    "nesco resource", "yoh", "judge group", "collabera",
    "infosys bpo", "wipro", "tata consultancy", "cognizant",
    "hcl technologies", "tech mahindra", "capgemini",
]


def _is_staffing_agency(company: str, raw_text: str) -> bool:
    """Detect if the employer is a staffing/temp agency."""
    company_lower = company.lower()
    text_lower = raw_text.lower()

    # Check against known staffing firms
    for firm in KNOWN_STAFFING_FIRMS:
        if firm in company_lower:
            return True

    # Check if company description includes staffing keywords
    staffing_hits = sum(1 for kw in STAFFING_KEYWORDS if kw in text_lower)
    if staffing_hits >= 2:
        return True

    # Check if the posting says "on behalf of" or "our client"
    client_patterns = [
        r"on behalf of",
        r"our client",
        r"client company",
        r"client is (a|an|seeking)",
        r"hiring for (a|an|our) client",
        r"direct hire .* client",
    ]
    for pattern in client_patterns:
        if re.search(pattern, text_lower):
            return True

    return False


def _detect_freelance_reliance(raw_text: str) -> int:
    """Count signals that the role relies on freelance/disposable labor."""
    text_lower = raw_text.lower()
    return sum(1 for kw in FREELANCE_RELIANCE_KEYWORDS if kw in text_lower)


def _detect_turnover_signals(raw_text: str) -> int:
    """Count signals of high-turnover culture."""
    text_lower = raw_text.lower()
    return sum(1 for signal in TURNOVER_SIGNALS if signal in text_lower)


async def _search_company_info(company: str) -> dict:
    """
    Use NewsAPI to gather general company information.
    Returns a dict with keys: article_count, articles, has_controversy.
    """
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key or api_key == "your_key_here":
        return {"article_count": -1, "articles": [], "has_controversy": False}

    results = {
        "article_count": 0,
        "articles": [],
        "has_controversy": False,
        "controversy_headline": "",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Search for general company presence
            response = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f'"{company}"',
                    "sortBy": "relevancy",
                    "pageSize": 5,
                    "apiKey": api_key,
                    "language": "en",
                },
            )

            if response.status_code == 200:
                data = response.json()
                results["article_count"] = data.get("totalResults", 0)
                results["articles"] = data.get("articles", [])

            # Search for controversies
            controversy_response = await client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f'"{company}" AND ("scandal" OR "fraud" OR "lawsuit" OR "investigation" OR "SEC" OR "FTC" OR "class action" OR "ponzi" OR "scam")',
                    "sortBy": "relevancy",
                    "pageSize": 3,
                    "apiKey": api_key,
                    "language": "en",
                },
            )

            if controversy_response.status_code == 200:
                cdata = controversy_response.json()
                if cdata.get("totalResults", 0) > 0:
                    articles = cdata.get("articles", [])
                    if articles:
                        results["has_controversy"] = True
                        results["controversy_headline"] = articles[0].get("title", "")

    except Exception as e:
        logger.error(f"company_intel search error: {e}")

    return results


async def company_intel(
    company: str, raw_text: str, title: str
) -> list[tuple[int, Optional[RedFlag]]]:
    """
    Analyze company legitimacy across multiple dimensions.
    Returns a list of (score_delta, optional_flag) tuples.
    """
    results: list[tuple[int, Optional[RedFlag]]] = []

    if not company:
        return results

    # 1. Staffing agency detection
    if _is_staffing_agency(company, raw_text):
        logger.info(f"company_intel: '{company}' detected as staffing/recruiting agency")
        results.append((
            WEIGHT_STAFFING_AGENCY,
            RedFlag(
                type="company",
                message=f"'{company}' appears to be a staffing agency or outsourcing firm — the actual employer is hidden",
                severity="high",
            ),
        ))

    # 2. Freelance/contractor reliance
    freelance_count = _detect_freelance_reliance(raw_text)
    if freelance_count >= 3:
        logger.info(f"company_intel: High freelance reliance ({freelance_count} signals)")
        results.append((
            WEIGHT_CONTROVERSIAL_MODEL,
            RedFlag(
                type="company",
                message=f"Role has {freelance_count} signals of freelance/contractor classification — may not be a real employee position",
                severity="high",
            ),
        ))
    elif freelance_count >= 1:
        results.append((
            WEIGHT_CONTROVERSIAL_MODEL // 2,
            RedFlag(
                type="company",
                message="Role mentions freelance or independent contractor terms — verify employment classification",
                severity="medium",
            ),
        ))

    # 3. High-turnover culture signals
    turnover_count = _detect_turnover_signals(raw_text)
    if turnover_count >= 3:
        logger.info(f"company_intel: High turnover signals ({turnover_count})")
        results.append((
            WEIGHT_HIGH_TURNOVER_SIGNALS,
            RedFlag(
                type="company",
                message=f"Job posting contains {turnover_count} high-turnover culture signals (hustle culture, always-on expectations)",
                severity="medium",
            ),
        ))

    # 4. News-based intelligence
    news_info = await _search_company_info(company)

    # No web presence at all
    if news_info["article_count"] == 0:
        logger.info(f"company_intel: No news presence for '{company}'")
        results.append((
            WEIGHT_NO_WEB_PRESENCE,
            RedFlag(
                type="company",
                message=f"No news coverage found for '{company}' — company may be too new, too small, or fictitious",
                severity="medium",
            ),
        ))

    # Controversy detected
    if news_info["has_controversy"]:
        headline = news_info["controversy_headline"]
        logger.info(f"company_intel: Controversy found for '{company}': {headline}")
        results.append((
            WEIGHT_CONTROVERSIAL_MODEL,
            RedFlag(
                type="company",
                message=f"Company linked to controversy: {headline[:120]}",
                severity="high",
            ),
        ))

    # 5. Role vs. company mismatch heuristics
    text_lower = raw_text.lower()

    # Tiny company hiring for very senior role
    senior_keywords = ["vp", "vice president", "director", "head of", "chief", "c-suite", "cto", "cfo", "coo"]
    is_senior_role = any(kw in title.lower() for kw in senior_keywords)
    tiny_signals = ["small team", "startup", "early stage", "seed stage", "pre-revenue", "founding"]
    is_tiny = sum(1 for s in tiny_signals if s in text_lower) >= 2

    if is_senior_role and is_tiny:
        results.append((
            WEIGHT_TINY_COMPANY_BIG_HIRE,
            RedFlag(
                type="structure",
                message="Senior leadership role at a very early-stage company — role may be aspirational rather than an active hire",
                severity="medium",
            ),
        ))

    # 6. Contract-to-hire / temp-to-perm patterns (often ghost jobs to fill quotas)
    cth_patterns = [
        r"contract[- ]to[- ]hire",
        r"temp[- ]to[- ]perm",
        r"contract with (possibility|option) (of|to)",
        r"potential for (full[- ]time|permanent|conversion)",
    ]
    for pattern in cth_patterns:
        if re.search(pattern, text_lower):
            results.append((
                5,
                RedFlag(
                    type="structure",
                    message="Contract-to-hire arrangement — conversion is not guaranteed and companies often cycle contractors without hiring",
                    severity="low",
                ),
            ))
            break

    return results
