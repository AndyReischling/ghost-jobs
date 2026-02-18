import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.schemas import (
    AnalyzeRequest,
    AnalysisResult,
    AnalyzeResponse,
    GhostScore,
    RedFlag,
    JobMetadata,
)
from app.services.scraper import scrape_job_page
from app.routers.analyze import analyze_job

router = APIRouter(prefix="/web", tags=["web"])
logger = logging.getLogger(__name__)


class ScrapeAndAnalyzeRequest(BaseModel):
    url: str


class ManualAnalyzeRequest(BaseModel):
    url: str
    title: str
    company: str
    rawText: str
    postedDate: Optional[str] = None
    platform: str = "unknown"


@router.post("/scrape-and-analyze", response_model=AnalyzeResponse)
async def scrape_and_analyze(request: ScrapeAndAnalyzeRequest) -> AnalysisResult:
    """Scrape a job posting URL and run ghost analysis."""
    logger.info(f"web: Scrape-and-analyze requested for {request.url}")

    try:
        metadata = await scrape_job_page(request.url)
    except Exception as e:
        error_msg = str(e)[:200]
        logger.error(f"web: Scraping failed for {request.url}: {error_msg}")
        return AnalysisResult(
            jobUrl=request.url,
            ghostScore=GhostScore(score=0, label="safe", color="green"),
            redFlags=[
                RedFlag(
                    type="parity",
                    message=f"Scrape failed: {error_msg}",
                    severity="low",
                )
            ],
            analyzedAt=datetime.now(timezone.utc).isoformat(),
            companyName="",
            jobTitle="Scrape failed — try manual mode",
        )

    analyze_request = AnalyzeRequest(url=request.url, metadata=metadata)
    return await analyze_job(analyze_request)


@router.post("/manual-analyze", response_model=AnalyzeResponse)
async def manual_analyze(request: ManualAnalyzeRequest) -> AnalysisResult:
    """Run ghost analysis on manually provided job details."""
    logger.info(f"web: Manual analyze for {request.company} — {request.title}")

    metadata = JobMetadata(
        url=request.url,
        title=request.title,
        company=request.company,
        postedDate=request.postedDate,
        rawText=request.rawText,
        platform=request.platform,
    )
    analyze_request = AnalyzeRequest(url=request.url, metadata=metadata)
    return await analyze_job(analyze_request)
