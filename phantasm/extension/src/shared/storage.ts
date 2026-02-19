import { ScanHistoryEntry } from './types';

const HISTORY_KEY = 'scanHistory';
const MAX_ENTRIES = 50;

export async function getScanHistory(): Promise<ScanHistoryEntry[]> {
  return new Promise((resolve) => {
    chrome.storage.local.get([HISTORY_KEY], (result) => {
      resolve(result[HISTORY_KEY] ?? []);
    });
  });
}

export async function addScanEntry(entry: ScanHistoryEntry): Promise<void> {
  const history = await getScanHistory();
  // Deduplicate by jobUrl: replace existing entry with same URL (keep latest result)
  const normalizedUrl = entry.jobUrl.replace(/\/$/, '');
  const filtered = history.filter((e) => e.jobUrl.replace(/\/$/, '') !== normalizedUrl);
  const updated = [entry, ...filtered].slice(0, MAX_ENTRIES);
  return new Promise((resolve) => {
    chrome.storage.local.set({ [HISTORY_KEY]: updated }, resolve);
  });
}

export async function clearHistory(): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove([HISTORY_KEY], resolve);
  });
}
