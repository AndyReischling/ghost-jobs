import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
from app.schemas import RedFlag

logger = logging.getLogger(__name__)

WEIGHT_FINANCIAL_LAYOFFS = 25

NEWS_API_BASE = "https://newsapi.org/v2/everything"


async def financial_health_check(
    company: str,
) -> tuple[int, Optional[RedFlag]]:
    """
    Query NewsAPI for recent layoff/hiring-freeze news about the company.
    Returns a (score_delta, optional_flag) tuple.
    """
    api_key = os.getenv("NEWS_API_KEY")

    if not api_key or api_key == "your_key_here":
        logger.warning("financial_health_check: NEWS_API_KEY not configured")
        return 0, None

    if not company:
        return 0, None

    from_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")
    query = (
        f'"{company}" AND ("layoffs" OR "hiring freeze" OR "downsizing" OR "job cuts")'
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                NEWS_API_BASE,
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "relevancy",
                    "pageSize": 5,
                    "apiKey": api_key,
                },
            )

            if response.status_code != 200:
                logger.error(
                    f"financial_health_check: NewsAPI returned {response.status_code}: "
                    f"{response.text[:200]}"
                )
                return 0, None

            data = response.json()
            total_results = data.get("totalResults", 0)
            articles = data.get("articles", [])

            if total_results > 0 and articles:
                top_article = articles[0]
                article_title = top_article.get("title", "Recent financial concerns")

                logger.info(
                    f"financial_health_check: Found {total_results} articles about "
                    f"{company} layoffs/freezes"
                )

                return WEIGHT_FINANCIAL_LAYOFFS, RedFlag(
                    type="financial",
                    message=f"Recent news: {article_title}",
                    severity="high",
                )

            logger.info(
                f"financial_health_check: No concerning news found for {company}"
            )
            return 0, None

    except Exception as e:
        logger.error(f"financial_health_check error: {e}")
        return 0, None
