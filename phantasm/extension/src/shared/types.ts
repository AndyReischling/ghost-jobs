export type Platform = 'linkedin' | 'indeed' | 'greenhouse' | 'lever' | 'unknown';
export type ScoreLabel = 'safe' | 'suspicious' | 'ghost';
export type ScoreColor = 'green' | 'yellow' | 'red';
export type FlagType = 'age' | 'parity' | 'sentiment' | 'financial' | 'company' | 'compensation' | 'structure';
export type Severity = 'low' | 'medium' | 'high';

export interface JobMetadata {
  url: string;
  title: string;
  company: string;
  postedDate: string | null;
  rawText: string;
  platform: Platform;
}

export interface GhostScore {
  score: number;
  label: ScoreLabel;
  color: ScoreColor;
}

export interface RedFlag {
  type: FlagType;
  message: string;
  severity: Severity;
}

export interface AnalysisResult {
  jobUrl: string;
  ghostScore: GhostScore;
  redFlags: RedFlag[];
  analyzedAt: string;
  companyName: string;
  jobTitle: string;
}

export interface ScanHistoryEntry extends AnalysisResult {
  id: string;
}

export interface AnalyzeRequest {
  url: string;
  metadata: JobMetadata;
}

export type AnalyzeResponse = AnalysisResult;
