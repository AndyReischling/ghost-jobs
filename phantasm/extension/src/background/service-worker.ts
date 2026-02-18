import { JobMetadata, AnalysisResult, ScanHistoryEntry } from '../shared/types';
import { addScanEntry } from '../shared/storage';

const API_URLS = [
  'https://www.doesthisjobexist.com',
  'http://localhost:8000',
];

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

async function analyzeJob(metadata: JobMetadata, tabId: number, tabUrl: string): Promise<void> {
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

  const entry: ScanHistoryEntry = {
    ...result,
    id: crypto.randomUUID(),
  };

  await addScanEntry(entry);

  chrome.tabs.sendMessage(tabId, {
    type: 'ANALYSIS_RESULT',
    payload: result,
  });

  const badgeColor = BADGE_COLOR_MAP[result.ghostScore.color] ?? '#6b7280';
  chrome.action.setBadgeText({ text: String(result.ghostScore.score), tabId });
  chrome.action.setBadgeBackgroundColor({ color: badgeColor, tabId });
}

chrome.runtime.onMessage.addListener(
  (message: { type: string; payload: JobMetadata }, sender, sendResponse) => {
    if (message.type === 'ANALYZE_JOB' && sender.tab?.id !== undefined) {
      const tabId = sender.tab.id;
      const tabUrl = sender.tab.url ?? message.payload.url;
      analyzeJob(message.payload, tabId, tabUrl);
      sendResponse({ received: true });
    }
  }
);
