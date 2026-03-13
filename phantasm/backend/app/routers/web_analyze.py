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
    url: str = "https://manual-entry"
    title: str = ""
    company: str = ""
    rawText: str = ""
    postedDate: Optional[str] = None
    platform: str = "unknown"
    salaryRange: Optional[str] = None
    jobSource: Optional[str] = None
    employmentType: Optional[str] = None
    experienceLevel: Optional[str] = None
    location: Optional[str] = None
    applicationMethod: Optional[str] = None


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

    # Detect LinkedIn login wall — server-side fetch gets login page, not job content
    if "linkedin.com" in request.url.lower():
        title_lower = (metadata.title or "").lower()
        is_login_page = (
            "sign in" in title_lower or "login" in title_lower
        ) and (not metadata.company or "unknown" in (metadata.company or "").lower())
        if is_login_page:
            return AnalysisResult(
                jobUrl=request.url,
                ghostScore=GhostScore(score=0, label="safe", color="green"),
                redFlags=[
                    RedFlag(
                        type="parity",
                        message="LinkedIn requires you to be logged in to view job content. Use the Phantasm browser extension while viewing the job on LinkedIn instead — it will analyze the page in your browser.",
                        severity="medium",
                    )
                ],
                analyzedAt=datetime.now(timezone.utc).isoformat(),
                companyName="",
                jobTitle="LinkedIn login required",
            )

    analyze_request = AnalyzeRequest(url=request.url, metadata=metadata)
    return await analyze_job(analyze_request)


@router.post("/manual-analyze", response_model=AnalyzeResponse)
async def manual_analyze(request: ManualAnalyzeRequest) -> AnalysisResult:
    """Run ghost analysis on manually provided job details."""
    logger.info(f"web: Manual analyze for {request.company} — {request.title}")

    # Build enriched raw text by prepending structured fields the user provided
    enriched_parts: list[str] = []
    if request.salaryRange:
        enriched_parts.append(f"Salary range: {request.salaryRange}")
    if request.employmentType:
        enriched_parts.append(f"Employment type: {request.employmentType}")
    if request.experienceLevel:
        enriched_parts.append(f"Experience level: {request.experienceLevel}")
    if request.location:
        enriched_parts.append(f"Location: {request.location}")
    if request.jobSource:
        enriched_parts.append(f"Found on: {request.jobSource}")
    if request.applicationMethod:
        enriched_parts.append(f"Application method: {request.applicationMethod}")

    raw_text = request.rawText
    if enriched_parts:
        raw_text = "\n".join(enriched_parts) + "\n\n" + raw_text

    metadata = JobMetadata(
        url=request.url,
        title=request.title,
        company=request.company,
        postedDate=request.postedDate,
        rawText=raw_text,
        platform=request.platform,
    )
    analyze_request = AnalyzeRequest(url=request.url, metadata=metadata)
    return await analyze_job(analyze_request)
