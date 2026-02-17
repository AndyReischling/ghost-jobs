from pydantic import BaseModel
from typing import Literal, Optional

Platform = Literal['linkedin', 'indeed', 'greenhouse', 'lever', 'unknown']
ScoreLabel = Literal['safe', 'suspicious', 'ghost']
ScoreColor = Literal['green', 'yellow', 'red']
FlagType = Literal[
    'age',          # posting age
    'parity',       # careers page cross-check
    'sentiment',    # JD quality / boilerplate
    'financial',    # layoffs / hiring freezes
    'company',      # company legitimacy
    'compensation', # pay transparency / unrealistic ranges
    'structure',    # role structure red flags
]
Severity = Literal['low', 'medium', 'high']


class JobMetadata(BaseModel):
    url: str
    title: str
    company: str
    postedDate: Optional[str] = None
    rawText: str
    platform: Platform


class GhostScore(BaseModel):
    score: int
    label: ScoreLabel
    color: ScoreColor


class RedFlag(BaseModel):
    type: FlagType
    message: str
    severity: Severity


class AnalysisResult(BaseModel):
    jobUrl: str
    ghostScore: GhostScore
    redFlags: list[RedFlag]
    analyzedAt: str
    companyName: str
    jobTitle: str


class AnalyzeRequest(BaseModel):
    url: str
    metadata: JobMetadata


AnalyzeResponse = AnalysisResult
