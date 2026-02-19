import { JobMetadata, AnalysisResult, ScanHistoryEntry } from '../shared/types';
import { addScanEntry } from '../shared/storage';

const API_URLS = [
  'https://www.doesthisjobexist.com',
  'http://localhost:8000',
];

const DEDUP_TTL_MS = 30 * 60 * 1000; // 30 min — reduces re-analysis and score variance for same job
const recentResults = new Map<string, { result: AnalysisResult; timestamp: number }>();
const pendingRequests = new Map<string, Promise<AnalysisResult>>();

function normalizeJobUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.origin + u.pathname.replace(/\/$/, '');
  } catch {
    return url;
  }
}

const BADGE_COLOR_MAP: Record<string, string> = {
  green: '#22c55e',
  yellow: '#eab308',
  red: '#ef4444',
};

function createFallbackResult(metadata: JobMetadata, url: string, errorMessage: string): AnalysisResult {
  return {
    jobUrl: url,
    ghostScore: { score: 0, label: 'safe', color: 'green' },
    redFlags: [{ type: 'parity', message: errorMessage, severity: 'low' }],
    analyzedAt: new Date().toISOString(),
    companyName: metadata.company,
    jobTitle: metadata.title,
  };
}

async function tryFetch(apiUrl: string, tabUrl: string, metadata: JobMetadata): Promise<AnalysisResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);

  const response = await fetch(`${apiUrl}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: tabUrl, metadata }),
    signal: controller.signal,
  });

  clearTimeout(timeout);

  if (!response.ok) {
    throw new Error(`API responded with status ${response.status}`);
  }

  return await response.json() as AnalysisResult;
}

function deliverResult(result: AnalysisResult, tabId: number): void {
  chrome.tabs.sendMessage(tabId, { type: 'ANALYSIS_RESULT', payload: result });
  const badgeColor = BADGE_COLOR_MAP[result.ghostScore.color] ?? '#6b7280';
  chrome.action.setBadgeText({ text: String(result.ghostScore.score), tabId });
  chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId });
}

async function fetchAnalysis(cacheKey: string, tabUrl: string, metadata: JobMetadata): Promise<AnalysisResult> {
  let result: AnalysisResult | null = null;

  for (const apiUrl of API_URLS) {
    try {
      result = await tryFetch(apiUrl, tabUrl, metadata);
      break;
    } catch {
      continue;
    }
  }

  if (!result) {
    result = createFallbackResult(metadata, tabUrl, 'Phantasm backend unreachable — is the server running?');
  }

  recentResults.set(cacheKey, { result, timestamp: Date.now() });

  const entry: ScanHistoryEntry = { ...result, id: crypto.randomUUID() };
  await addScanEntry(entry);

  return result;
}

async function analyzeJob(metadata: JobMetadata, tabId: number, tabUrl: string): Promise<void> {
  const cacheKey = normalizeJobUrl(tabUrl);

  // Return cached result immediately
  const cached = recentResults.get(cacheKey);
  if (cached && Date.now() - cached.timestamp < DEDUP_TTL_MS) {
    deliverResult(cached.result, tabId);
    return;
  }

  // If an analysis is already in-flight for this URL, wait for it
  const pending = pendingRequests.get(cacheKey);
  if (pending) {
    const result = await pending;
    deliverResult(result, tabId);
    return;
  }

  // Start new analysis and track the promise
  const promise = fetchAnalysis(cacheKey, tabUrl, metadata);
  pendingRequests.set(cacheKey, promise);

  try {
    const result = await promise;
    deliverResult(result, tabId);
  } finally {
    pendingRequests.delete(cacheKey);
  }
}

chrome.runtime.onMessage.addListener(
  (message: { type: string; payload: JobMetadata | AnalysisResult }, sender, sendResponse) => {
    if (message.type === 'ANALYZE_JOB' && sender.tab?.id !== undefined) {
      const tabId = sender.tab.id;
      const tabUrl = sender.tab.url ?? (message.payload as JobMetadata).url;
      analyzeJob(message.payload as JobMetadata, tabId, tabUrl);
      sendResponse({ received: true });
    }

    if (message.type === 'CLOSED_LISTING' && sender.tab?.id !== undefined) {
      const result = message.payload as AnalysisResult;
      const entry: ScanHistoryEntry = { ...result, id: crypto.randomUUID() };
      addScanEntry(entry);
      const badgeColor = BADGE_COLOR_MAP[result.ghostScore.color] ?? '#6b7280';
      chrome.action.setBadgeText({ text: String(result.ghostScore.score), tabId: sender.tab.id });
      chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId: sender.tab.id });
      sendResponse({ received: true });
    }
  }
);
