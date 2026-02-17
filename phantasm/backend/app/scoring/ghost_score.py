from datetime import datetime, timezone
from typing import Optional
from app.schemas import (
    JobMetadata,
    GhostScore,
    RedFlag,
    AnalysisResult,
)

# --- Tunable weights ---
WEIGHT_AGE_OLD = 30           # posted > 60 days ago
WEIGHT_AGE_MEDIUM = 15        # posted 30–60 days ago
WEIGHT_PARITY_FAIL = 25       # not found on careers page
WEIGHT_PARITY_PASS = -10      # found on careers page (floor 0)
WEIGHT_FINANCIAL_LAYOFFS = 25  # confirmed recent layoffs
WEIGHT_FINANCIAL_FREEZE = 15   # hiring freeze reported
WEIGHT_SENTIMENT_MAX = 20     # JD >80% template similarity (LLM)
WEIGHT_SENTIMENT_MED = 10     # JD 50–80% template similarity (LLM)

SCORE_CAP = 100
THRESHOLD_GHOST = 70
THRESHOLD_SUSPICIOUS = 40


def _calculate_age_delta(posted_date: Optional[str]) -> tuple[int, Optional[RedFlag]]:
    """Calculate score delta based on posting age."""
    if not posted_date:
        return 0, None

    try:
        posted = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_old = (now - posted).days

        if days_old > 60:
            return WEIGHT_AGE_OLD, RedFlag(
                type="age",
                message=f"Posted {days_old} days ago — stale listings often indicate ghost jobs",
                severity="high",
            )
        elif days_old > 30:
            return WEIGHT_AGE_MEDIUM, RedFlag(
                type="age",
                message=f"Posted {days_old} days ago — listing is aging",
                severity="medium",
            )
    except (ValueError, TypeError):
        pass

    return 0, None


def calculate_ghost_score(
    metadata: JobMetadata,
    job_url: str,
    parity: tuple[int, Optional[RedFlag]],
    financial: tuple[int, Optional[RedFlag]],
    llm: tuple[int, Optional[RedFlag]],
    heuristics: Optional[list[tuple[int, Optional[RedFlag]]]] = None,
) -> AnalysisResult:
    """
    Aggregate all signal deltas into a single Ghost Score.
    Each input tuple is (score_delta, optional_red_flag).
    Heuristics is a list of multiple (delta, flag) tuples from text analysis.
    """
    score = 0
    red_flags: list[RedFlag] = []

    # Age signal
    age_delta, age_flag = _calculate_age_delta(metadata.postedDate)
    score += age_delta
    if age_flag:
        red_flags.append(age_flag)

    # Parity signal
    parity_delta, parity_flag = parity
    score += parity_delta
    if parity_flag:
        red_flags.append(parity_flag)

    # Financial health signal
    financial_delta, financial_flag = financial
    score += financial_delta
    if financial_flag:
        red_flags.append(financial_flag)

    # LLM / sentiment signal
    llm_delta, llm_flag = llm
    score += llm_delta
    if llm_flag:
        red_flags.append(llm_flag)

    # Heuristic signals (text-based, no API keys)
    if heuristics:
        for h_delta, h_flag in heuristics:
            score += h_delta
            if h_flag:
                red_flags.append(h_flag)

    # Clamp score
    score = max(0, min(score, SCORE_CAP))

    # Derive label and color
    if score >= THRESHOLD_GHOST:
        label = "ghost"
        color = "red"
    elif score >= THRESHOLD_SUSPICIOUS:
        label = "suspicious"
        color = "yellow"
    else:
        label = "safe"
        color = "green"

    return AnalysisResult(
        jobUrl=job_url,
        ghostScore=GhostScore(score=score, label=label, color=color),
        redFlags=red_flags,
        analyzedAt=datetime.now(timezone.utc).isoformat(),
        companyName=metadata.company,
        jobTitle=metadata.title,
    )
