import json
import logging
import os
import re
from typing import Optional
import anthropic
from app.schemas import RedFlag

logger = logging.getLogger(__name__)

WEIGHT_SENTIMENT_MAX = 20
WEIGHT_SENTIMENT_MED = 10

SYSTEM_PROMPT = """You are an expert at identifying ghost job postings — jobs that companies post with no real intention of filling.

Analyze the job description and return ONLY a JSON object — no markdown, no explanation — with these fields:

{
  "templateScore": <int 0-100>,
  "legitimacyScore": <int 0-100>,
  "redFlags": [<string>, ...],
  "reasoning": "<one sentence>"
}

templateScore: How generic/boilerplate is this JD? 100 = pure copy-paste template. 0 = highly specific custom role.

legitimacyScore: How likely is this a real, active hire? 100 = definitely real. 0 = almost certainly a ghost job.
Consider: specificity of responsibilities, realistic requirements, clear team/reporting structure, genuine business need expressed, salary transparency.

redFlags: List specific concerns you notice. Examples:
- "No specific projects or deliverables mentioned"
- "Requirements span multiple unrelated disciplines"  
- "Boilerplate equal opportunity statement is longer than the actual job description"
- "Title doesn't match the described responsibilities"
- "Sounds like compliance hiring (posting for legal/visa reasons with a pre-selected candidate)"

Keep redFlags to 3 items max. Only include genuine concerns, not generic observations.
Only flag missing salary/compensation if you have searched the ENTIRE provided text and found NO dollar amounts, salary ranges, or compensation figures. If any pay information exists, do NOT include a salary-related red flag."""


def _parse_llm_response(text: str) -> dict:
    """Parse the LLM response, stripping any accidental markdown fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


async def llm_analysis(
    raw_text: str, job_title: str
) -> tuple[int, Optional[RedFlag]]:
    """
    Call the Anthropic API for deep JD analysis.
    Returns a (score_delta, optional_flag) tuple for the template score,
    plus additional flags are returned via the enhanced router.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or api_key == "your_key_here":
        logger.warning("llm_analysis: ANTHROPIC_API_KEY not configured")
        return 0, None

    if not raw_text:
        return 0, None

    truncated_text = raw_text[:6000]  # More context so salary (often near end) is included

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Job Title: {job_title}\n\n"
                        f"Job Description:\n{truncated_text}"
                    ),
                }
            ],
        )

        response_text = message.content[0].text
        parsed = _parse_llm_response(response_text)

        template_score = int(parsed.get("templateScore", 0))
        legitimacy_score = int(parsed.get("legitimacyScore", 100))
        llm_red_flags = parsed.get("redFlags", [])
        reasoning = parsed.get("reasoning", "")

        logger.info(
            f"llm_analysis: template={template_score}, legitimacy={legitimacy_score} "
            f"for '{job_title}' — {reasoning}"
        )

        # Calculate delta from template score
        delta = 0
        flag = None
        if template_score > 80:
            delta = WEIGHT_SENTIMENT_MAX
            flag = RedFlag(
                type="sentiment",
                message=f"AI analysis: JD is {template_score}% boilerplate — {reasoning}",
                severity="high",
            )
        elif template_score >= 50:
            delta = WEIGHT_SENTIMENT_MED
            flag = RedFlag(
                type="sentiment",
                message=f"AI analysis: JD is {template_score}% generic — {reasoning}",
                severity="medium",
            )

        return delta, flag

    except json.JSONDecodeError as e:
        logger.error(f"llm_analysis: Failed to parse LLM response as JSON: {e}")
        return 0, None
    except Exception as e:
        logger.error(f"llm_analysis error: {e}")
        return 0, None


async def llm_deep_analysis(
    raw_text: str, job_title: str
) -> list[tuple[int, Optional[RedFlag]]]:
    """
    Extended LLM analysis that returns multiple signals.
    Called separately from the basic llm_analysis for the extra red flags and legitimacy score.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key or api_key == "your_key_here":
        return []

    if not raw_text:
        return []

    truncated_text = raw_text[:6000]  # More context so salary (often near end) is included
    results: list[tuple[int, Optional[RedFlag]]] = []

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Job Title: {job_title}\n\n"
                        f"Job Description:\n{truncated_text}"
                    ),
                }
            ],
        )

        response_text = message.content[0].text
        parsed = _parse_llm_response(response_text)

        legitimacy_score = int(parsed.get("legitimacyScore", 100))
        llm_red_flags = parsed.get("redFlags", [])

        # Low legitimacy score
        if legitimacy_score < 20:
            results.append((
                20,
                RedFlag(
                    type="sentiment",
                    message=f"AI legitimacy assessment: {legitimacy_score}/100 — this posting has strong ghost job indicators",
                    severity="high",
                ),
            ))
        elif legitimacy_score < 40:
            results.append((
                14,
                RedFlag(
                    type="sentiment",
                    message=f"AI legitimacy assessment: {legitimacy_score}/100 — multiple concerns about whether this is a genuine hire",
                    severity="high",
                ),
            ))
        elif legitimacy_score < 60:
            results.append((
                8,
                RedFlag(
                    type="sentiment",
                    message=f"AI legitimacy assessment: {legitimacy_score}/100 — some concerns about this listing",
                    severity="medium",
                ),
            ))

        # Individual red flags from LLM — each is a meaningful signal
        for i, flag_text in enumerate(llm_red_flags[:3]):
            if isinstance(flag_text, str) and len(flag_text) > 10:
                severity = "high" if i == 0 else "medium"
                weight = 8 if i == 0 else 5
                results.append((
                    weight,
                    RedFlag(
                        type="sentiment",
                        message=f"AI detected: {flag_text}",
                        severity=severity,
                    ),
                ))

        return results

    except Exception as e:
        logger.error(f"llm_deep_analysis error: {e}")
        return []
