import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from app.schemas import AnalyzeRequest, AnalyzeResponse, RedFlag, GhostScore, AnalysisResult
from app.services.parity_check import parity_check
from app.services.financial_health import financial_health_check
from app.services.llm_analysis import llm_analysis, llm_deep_analysis
from app.services.heuristic_analysis import heuristic_analysis
from app.services.company_intel import company_intel
from app.scoring.ghost_score import calculate_ghost_score

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_job(request: AnalyzeRequest) -> AnalysisResult:
    logger.info(
        f"[{datetime.now(timezone.utc).isoformat()}] Analyzing: "
        f"{request.metadata.company} — {request.metadata.title}"
    )

    try:
        # Run all 6 analysis services in parallel
        (
            parity_result,
            financial_result,
            llm_result,
            heuristic_results,
            company_results,
            llm_deep_results,
        ) = await asyncio.gather(
            parity_check(request.metadata.company, request.metadata.title),
            financial_health_check(request.metadata.company),
            llm_analysis(request.metadata.rawText, request.metadata.title),
            heuristic_analysis(request.metadata.rawText, request.metadata.title),
            company_intel(request.metadata.company, request.metadata.rawText, request.metadata.title),
            llm_deep_analysis(request.metadata.rawText, request.metadata.title),
            return_exceptions=True,
        )

        # Merge heuristic + company + llm_deep results into one list
        all_extra_signals: list = []

        if not isinstance(heuristic_results, Exception) and heuristic_results:
            all_extra_signals.extend(heuristic_results)

        if not isinstance(company_results, Exception) and company_results:
            all_extra_signals.extend(company_results)

        if not isinstance(llm_deep_results, Exception) and llm_deep_results:
            all_extra_signals.extend(llm_deep_results)

        result = calculate_ghost_score(
            metadata=request.metadata,
            job_url=request.url,
            parity=parity_result if not isinstance(parity_result, Exception) else (0, None),
            financial=financial_result if not isinstance(financial_result, Exception) else (0, None),
            llm=llm_result if not isinstance(llm_result, Exception) else (0, None),
            heuristics=all_extra_signals if all_extra_signals else None,
        )

        logger.info(
            f"  -> Ghost Score: {result.ghostScore.score} ({result.ghostScore.label}) "
            f"with {len(result.redFlags)} flags"
        )
        return result

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return AnalysisResult(
            jobUrl=request.url,
            ghostScore=GhostScore(score=0, label="safe", color="green"),
            redFlags=[
                RedFlag(
                    type="parity",
                    message=f"Analysis error: {str(e)}",
                    severity="low",
                )
            ],
            analyzedAt=datetime.now(timezone.utc).isoformat(),
            companyName=request.metadata.company,
            jobTitle=request.metadata.title,
        )
