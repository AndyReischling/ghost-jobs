"""
Text-based heuristic analysis of job descriptions.
No API keys required — works entirely on pattern matching and text statistics.
"""

import logging
import re
from typing import Optional
from app.schemas import RedFlag

logger = logging.getLogger(__name__)

# --- Tunable weights ---
WEIGHT_VAGUE_TITLE = 10
WEIGHT_BOILERPLATE_HEAVY = 15
WEIGHT_NO_SPECIFICS = 12
WEIGHT_EXCESSIVE_REQUIREMENTS = 10
WEIGHT_REPOST_SIGNALS = 15
WEIGHT_KITCHEN_SINK = 12
WEIGHT_SHORT_JD = 10
WEIGHT_SALARY_RED_FLAG = 8
WEIGHT_APPLICATION_RED_FLAG = 10
WEIGHT_URGENCY_MANIPULATION = 8
WEIGHT_COPY_PASTE_ARTIFACTS = 12

# Phrases that signal a generic/template JD
BOILERPLATE_PHRASES = [
    "fast-paced environment",
    "dynamic team",
    "passionate individual",
    "self-starter",
    "wear many hats",
    "hit the ground running",
    "rockstar",
    "ninja",
    "guru",
    "synergy",
    "think outside the box",
    "go-getter",
    "team player",
    "excellent communication skills",
    "detail-oriented",
    "results-driven",
    "work hard play hard",
    "like a family",
    "competitive salary",
    "exciting opportunity",
    "unique opportunity",
    "world-class",
    "best-in-class",
    "move the needle",
    "leverage",
    "circle back",
    "low-hanging fruit",
    "bandwidth",
    "alignment",
    "take ownership",
    "proactive",
    "strong work ethic",
    "able to thrive",
    "other duties as assigned",
    "duties as needed",
    "flexible schedule required",
    "comfortable with ambiguity",
    "bias for action",
    "sense of urgency",
]

# Vague/meaningless job titles
VAGUE_TITLE_PATTERNS = [
    r"^(associate|specialist|coordinator|representative|analyst)$",
    r"various\s+(positions|roles|openings)",
    r"multiple\s+(positions|roles|openings)",
    r"general\s+application",
    r"talent\s+(pool|community|network)",
    r"future\s+(opening|role|opportunity|consideration)",
    r"expression\s+of\s+interest",
    r"team\s+member",
    r"brand\s+ambassador",
]

# Signals that a posting has been recycled/reposted
REPOST_SIGNALS = [
    "reposted",
    "re-posted",
    "updated posting",
    "previously listed",
    "ongoing recruitment",
    "continuous posting",
    "evergreen",
    "pipeline",
    "talent pool",
    "always accepting",
    "rolling basis",
    "open until filled",
    "continuous recruitment",
]

# Signals of unrealistic requirements (kitchen-sink listings)
KITCHEN_SINK_TECHS = [
    "java", "python", "javascript", "typescript", "c++", "c#", "ruby",
    "go", "rust", "scala", "kotlin", "swift", "php", "perl",
    "react", "angular", "vue", "svelte", "next.js", "nuxt",
    "node.js", "django", "flask", "spring", "rails",
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
    "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
    "kafka", "rabbitmq", "graphql", "rest",
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "spark", "hadoop",
]

# Application process red flags
APPLICATION_RED_FLAGS = [
    "apply on company website",  # redirecting away from the job board
    "send resume to",            # email-based = often not tracked
    "email your resume",
    "apply via email",
    "no phone calls",
    "do not contact",
    "no recruiters",
]

# Urgency / pressure tactics
URGENCY_PHRASES = [
    "apply immediately",
    "position will be filled quickly",
    "don't miss this opportunity",
    "limited time",
    "act fast",
    "apply today",
    "urgent hire",
    "immediate need",
    "asap",
    "time-sensitive",
]


def _count_boilerplate(text: str) -> int:
    text_lower = text.lower()
    return sum(1 for phrase in BOILERPLATE_PHRASES if phrase in text_lower)


def _is_vague_title(title: str) -> bool:
    title_lower = title.lower().strip()
    for pattern in VAGUE_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False


def _has_repost_signals(text: str) -> bool:
    text_lower = text.lower()
    return any(signal in text_lower for signal in REPOST_SIGNALS)


def _count_tech_requirements(text: str) -> int:
    text_lower = text.lower()
    return sum(1 for tech in KITCHEN_SINK_TECHS if tech in text_lower)


def _has_specifics(text: str) -> bool:
    specificity_signals = [
        r"\d+\s*(years?|months?)\s*(of)?\s*(experience|exp)",
        r"\$[\d,]+",
        r"\d+%",
        r"team of \d+",
        r"report(ing)? to",
        r"(q[1-4]|quarter)",
        r"(series [a-d]|seed|ipo)",
        r"\d+ (employees|people|engineers|developers)",
        r"(slack|jira|confluence|notion|figma|linear|asana|monday)",
        r"(annual|quarterly) review",
        r"\d+\s*(direct reports|headcount)",
    ]
    text_lower = text.lower()
    matches = sum(1 for p in specificity_signals if re.search(p, text_lower))
    return matches >= 2


def _word_count(text: str) -> int:
    return len(text.split())


def _detect_salary_issues(text: str) -> list[tuple[int, Optional[RedFlag]]]:
    """Analyze compensation transparency and realism."""
    results: list[tuple[int, Optional[RedFlag]]] = []
    text_lower = text.lower()

    # Wide salary range (e.g., $50k-$150k = 3x spread)
    salary_ranges = re.findall(
        r"\$\s*([\d,]+)\s*(?:k|K|,000)?\s*(?:-|to|–)\s*\$\s*([\d,]+)\s*(?:k|K|,000)?",
        text
    )
    for low_str, high_str in salary_ranges:
        low = int(low_str.replace(",", ""))
        high = int(high_str.replace(",", ""))
        # Normalize if using "k" notation
        if low < 1000:
            low *= 1000
        if high < 1000:
            high *= 1000
        if high > 0 and low > 0:
            ratio = high / low
            if ratio >= 3.0:
                results.append((
                    WEIGHT_SALARY_RED_FLAG,
                    RedFlag(
                        type="compensation",
                        message=f"Salary range is extremely wide (${low:,}–${high:,}, a {ratio:.1f}x spread) — vague compensation suggests the role is not well-defined",
                        severity="medium",
                    ),
                ))
                break
            elif ratio >= 2.0:
                results.append((
                    WEIGHT_SALARY_RED_FLAG // 2,
                    RedFlag(
                        type="compensation",
                        message=f"Salary range is broad (${low:,}–${high:,}) — may indicate the role scope is unclear",
                        severity="low",
                    ),
                ))
                break

    # "Competitive salary" with no numbers = hiding compensation
    if "competitive" in text_lower and ("salary" in text_lower or "compensation" in text_lower):
        has_numbers = bool(re.search(r"\$\s*[\d,]+", text))
        if not has_numbers:
            results.append((
                WEIGHT_SALARY_RED_FLAG // 2,
                RedFlag(
                    type="compensation",
                    message="Claims 'competitive salary' but provides no actual numbers — lack of pay transparency is a red flag",
                    severity="low",
                ),
            ))

    # "DOE" (depends on experience) with no range
    doe_patterns = [r"\bdoe\b", r"depends on experience", r"commensurate with experience", r"based on experience"]
    has_doe = any(re.search(p, text_lower) for p in doe_patterns)
    has_range = bool(re.search(r"\$\s*[\d,]+", text))
    if has_doe and not has_range:
        results.append((
            WEIGHT_SALARY_RED_FLAG // 2,
            RedFlag(
                type="compensation",
                message="Compensation listed as 'depends on experience' with no range — common in ghost postings that aren't budgeted",
                severity="low",
            ),
        ))

    return results


def _detect_application_red_flags(text: str) -> list[tuple[int, Optional[RedFlag]]]:
    """Detect suspicious application process signals."""
    results: list[tuple[int, Optional[RedFlag]]] = []
    text_lower = text.lower()

    # Redirecting to external site
    redirect_count = sum(1 for flag in APPLICATION_RED_FLAGS if flag in text_lower)
    if redirect_count >= 2:
        results.append((
            WEIGHT_APPLICATION_RED_FLAG,
            RedFlag(
                type="structure",
                message="Application process has multiple red flags (external redirects, email-only, no-contact policies)",
                severity="medium",
            ),
        ))

    # Urgency manipulation
    urgency_count = sum(1 for phrase in URGENCY_PHRASES if phrase in text_lower)
    if urgency_count >= 2:
        results.append((
            WEIGHT_URGENCY_MANIPULATION,
            RedFlag(
                type="structure",
                message=f"Uses {urgency_count} urgency phrases to pressure quick applications — legitimate roles don't need high-pressure tactics",
                severity="medium",
            ),
        ))

    return results


def _detect_copy_paste_artifacts(text: str) -> Optional[tuple[int, RedFlag]]:
    """Detect signs that the JD was copy-pasted from a template."""
    signals = 0

    # Placeholder text left in
    placeholders = [
        r"\[company\s*name\]",
        r"\[insert\s",
        r"\{company\}",
        r"<company>",
        r"lorem ipsum",
        r"xxx",
        r"\[tbd\]",
        r"\[fill in\]",
    ]
    text_lower = text.lower()
    for p in placeholders:
        if re.search(p, text_lower):
            signals += 2

    # Multiple different company names mentioned (copy-paste from another company's JD)
    # This is hard to detect without knowing the company, but we can look for patterns

    # "About [Company]" section that doesn't match the posting company
    # Duplicate sections (same paragraph appearing twice)
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    seen = set()
    for para in paragraphs:
        normalized = para.lower().strip()[:100]
        if normalized in seen:
            signals += 1
        seen.add(normalized)

    if signals >= 2:
        return (
            WEIGHT_COPY_PASTE_ARTIFACTS,
            RedFlag(
                type="sentiment",
                message="Job description contains copy-paste artifacts (placeholder text, duplicate sections) — likely recycled from a template",
                severity="high",
            ),
        )

    return None


async def heuristic_analysis(
    raw_text: str, title: str
) -> list[tuple[int, Optional[RedFlag]]]:
    """
    Run multiple text heuristics on the job description.
    Returns a list of (score_delta, optional_flag) tuples.
    """
    results: list[tuple[int, Optional[RedFlag]]] = []

    if not raw_text:
        return results

    word_count = _word_count(raw_text)

    # 1. Vague title check
    if _is_vague_title(title):
        logger.info(f"heuristic: Vague title detected: '{title}'")
        results.append((
            WEIGHT_VAGUE_TITLE,
            RedFlag(
                type="sentiment",
                message=f"Job title '{title}' is vague or suggests a talent pool, not a real opening",
                severity="medium",
            ),
        ))

    # 2. Boilerplate density
    boilerplate_count = _count_boilerplate(raw_text)
    if boilerplate_count >= 6:
        logger.info(f"heuristic: High boilerplate density ({boilerplate_count} phrases)")
        results.append((
            WEIGHT_BOILERPLATE_HEAVY,
            RedFlag(
                type="sentiment",
                message=f"Job description contains {boilerplate_count} generic buzzword phrases — likely a template",
                severity="high",
            ),
        ))
    elif boilerplate_count >= 3:
        logger.info(f"heuristic: Moderate boilerplate ({boilerplate_count} phrases)")
        results.append((
            WEIGHT_BOILERPLATE_HEAVY // 2,
            RedFlag(
                type="sentiment",
                message=f"Job description contains {boilerplate_count} common buzzword phrases",
                severity="medium",
            ),
        ))

    # 3. Lack of specifics
    if word_count > 100 and not _has_specifics(raw_text):
        logger.info("heuristic: No concrete specifics found in JD")
        results.append((
            WEIGHT_NO_SPECIFICS,
            RedFlag(
                type="sentiment",
                message="No concrete details found — no team size, metrics, projects, or specific deliverables mentioned",
                severity="medium",
            ),
        ))

    # 4. Kitchen-sink requirements
    tech_count = _count_tech_requirements(raw_text)
    if tech_count >= 12:
        logger.info(f"heuristic: Kitchen-sink listing ({tech_count} distinct technologies)")
        results.append((
            WEIGHT_KITCHEN_SINK,
            RedFlag(
                type="sentiment",
                message=f"Lists {tech_count} distinct technologies — unrealistic requirements suggest a placeholder listing",
                severity="high",
            ),
        ))
    elif tech_count >= 8:
        results.append((
            WEIGHT_KITCHEN_SINK // 2,
            RedFlag(
                type="sentiment",
                message=f"Lists {tech_count} distinct technologies — unusually broad requirements",
                severity="medium",
            ),
        ))

    # 5. Repost/evergreen signals
    if _has_repost_signals(raw_text):
        logger.info("heuristic: Repost/evergreen signals detected")
        results.append((
            WEIGHT_REPOST_SIGNALS,
            RedFlag(
                type="age",
                message="Posting contains language suggesting it is recycled, evergreen, or a talent pipeline",
                severity="high",
            ),
        ))

    # 6. Extremely short JD
    if 0 < word_count < 80:
        logger.info(f"heuristic: Very short JD ({word_count} words)")
        results.append((
            WEIGHT_SHORT_JD,
            RedFlag(
                type="sentiment",
                message=f"Job description is only {word_count} words — too brief to be a real, detailed listing",
                severity="medium",
            ),
        ))

    # 7. Excessive years of experience
    exp_matches = re.findall(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)", raw_text.lower())
    if exp_matches:
        max_exp = max(int(y) for y in exp_matches)
        title_lower = title.lower()
        is_junior_mid = any(kw in title_lower for kw in ["junior", "jr", "entry", "associate", "intern"])
        if max_exp >= 10 and is_junior_mid:
            results.append((
                WEIGHT_EXCESSIVE_REQUIREMENTS,
                RedFlag(
                    type="structure",
                    message=f"Requires {max_exp}+ years experience for a junior/mid-level title — contradictory requirements",
                    severity="high",
                ),
            ))
        elif max_exp >= 15:
            results.append((
                WEIGHT_EXCESSIVE_REQUIREMENTS,
                RedFlag(
                    type="structure",
                    message=f"Requires {max_exp}+ years experience — extremely high bar may indicate a pre-selected candidate",
                    severity="medium",
                ),
            ))

    # 8. Salary / compensation analysis
    results.extend(_detect_salary_issues(raw_text))

    # 9. Application process red flags
    results.extend(_detect_application_red_flags(raw_text))

    # 10. Copy-paste artifacts
    copy_paste = _detect_copy_paste_artifacts(raw_text)
    if copy_paste:
        results.append(copy_paste)

    return results
