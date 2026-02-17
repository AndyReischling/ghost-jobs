import { Platform, JobMetadata, AnalysisResult } from '../shared/types';

function detectPlatform(): Platform {
  const hostname = window.location.hostname;
  if (hostname.includes('linkedin.com')) return 'linkedin';
  if (hostname.includes('indeed.com')) return 'indeed';
  if (hostname.includes('greenhouse.io')) return 'greenhouse';
  if (hostname.includes('lever.co')) return 'lever';
  return 'unknown';
}

function getTextContent(selector: string): string {
  const el = document.querySelector(selector);
  return el?.textContent?.trim() ?? '';
}

function getFirstMatch(...selectors: string[]): string {
  for (const sel of selectors) {
    const text = getTextContent(sel);
    if (text) return text;
  }
  return '';
}

function extractJobMetadata(): JobMetadata {
  const platform = detectPlatform();
  const url = window.location.href;
  let title = '';
  let company = '';
  let postedDate: string | null = null;

  switch (platform) {
    case 'linkedin':
      title = getFirstMatch(
        '.job-details-jobs-unified-top-card__job-title',
        '.jobs-unified-top-card__job-title',
        '.t-24.t-bold.inline',
        '.job-details-jobs-unified-top-card__job-title a',
        '.jobs-unified-top-card__job-title a',
        'h1.t-24',
        'h1.t-20',
        'h1',
        '.job-title',
        '[class*="jobTitle"]',
        '[class*="job-title"]',
      );
      company = getFirstMatch(
        '.job-details-jobs-unified-top-card__company-name',
        '.jobs-unified-top-card__company-name',
        '.job-details-jobs-unified-top-card__company-name a',
        '.jobs-unified-top-card__company-name a',
        '.artdeco-entity-lockup__subtitle',
        '[class*="company-name"]',
        '[class*="companyName"]',
      );
      postedDate = getFirstMatch(
        '.jobs-unified-top-card__posted-date',
        '[class*="posted-date"]',
        '.job-details-jobs-unified-top-card__primary-description-container span',
      ) || null;
      break;

    case 'indeed':
      title = getFirstMatch(
        'h1.jobsearch-JobInfoHeader-title',
        '[data-jk]',
        'h1[class*="JobTitle"]',
        'h1',
      );
      company = getFirstMatch(
        '.jobsearch-InlineCompanyRating-companyName',
        '[data-company-name]',
        '[class*="CompanyName"]',
      );
      postedDate = getFirstMatch('.date', '[class*="posted"]') || null;
      break;

    case 'greenhouse':
      title = getFirstMatch('h1.app-title', 'h1');
      company =
        getFirstMatch('.company-name') ||
        window.location.hostname.split('.')[0];
      break;

    case 'lever':
      title = getFirstMatch('.posting-headline h2', 'h2');
      company = window.location.hostname.split('.')[0];
      break;

    default:
      title = document.title;
      break;
  }

  const rawText = document.body.innerText.trim().slice(0, 8000);

  return { url, title, company, postedDate, rawText, platform };
}

function getScoreColorHex(color: string): string {
  const colorMap: Record<string, string> = {
    green: '#22c55e',
    yellow: '#eab308',
    red: '#ef4444',
  };
  return colorMap[color] ?? '#6b7280';
}

function getLabelText(label: string): string {
  const labelMap: Record<string, string> = {
    safe: 'SAFE',
    suspicious: 'SUSPICIOUS',
    ghost: 'GHOST',
  };
  return labelMap[label] ?? label.toUpperCase();
}

let sidebarVisible = false;

function injectGhostMeter(result: AnalysisResult): void {
  try {
    const existingBadge = document.getElementById('phantasm-badge');
    const colorHex = getScoreColorHex(result.ghostScore.color);
    const labelText = getLabelText(result.ghostScore.label);

    if (existingBadge) {
      const circle = existingBadge.querySelector(
        '#phantasm-badge-circle'
      ) as HTMLElement;
      const scoreText = existingBadge.querySelector(
        '#phantasm-badge-score'
      ) as HTMLElement;
      const labelEl = existingBadge.querySelector(
        '#phantasm-badge-label'
      ) as HTMLElement;

      if (circle) {
        circle.style.backgroundColor = colorHex;
        circle.style.animation = 'none';
      }
      if (scoreText) scoreText.textContent = String(result.ghostScore.score);
      if (labelEl) {
        labelEl.textContent = labelText;
        labelEl.style.color = colorHex;
      }
      return;
    }

    const badge = document.createElement('div');
    badge.id = 'phantasm-badge';
    badge.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      cursor: pointer;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      user-select: none;
      transition: transform 0.2s ease;
    `;

    const circle = document.createElement('div');
    circle.id = 'phantasm-badge-circle';
    circle.style.cssText = `
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background-color: ${colorHex};
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      transition: background-color 0.3s ease;
    `;

    const scoreText = document.createElement('span');
    scoreText.id = 'phantasm-badge-score';
    scoreText.textContent = String(result.ghostScore.score);
    scoreText.style.cssText = `
      color: #ffffff;
      font-size: 18px;
      font-weight: 700;
      line-height: 1;
    `;
    circle.appendChild(scoreText);

    const label = document.createElement('div');
    label.id = 'phantasm-badge-label';
    label.textContent = labelText;
    label.style.cssText = `
      color: ${colorHex};
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
    `;

    badge.appendChild(circle);
    badge.appendChild(label);

    badge.addEventListener('mouseenter', () => {
      badge.style.transform = 'scale(1.1)';
    });
    badge.addEventListener('mouseleave', () => {
      badge.style.transform = 'scale(1)';
    });

    badge.addEventListener('click', () => {
      toggleSidebar(result);
    });

    document.body.appendChild(badge);
  } catch (err) {
    // Silently fail — never break the host page
  }
}

function toggleSidebar(result: AnalysisResult): void {
  const existingSidebar = document.getElementById('phantasm-sidebar-container');

  if (sidebarVisible && existingSidebar) {
    existingSidebar.style.transform = 'translateX(100%)';
    setTimeout(() => {
      existingSidebar.remove();
    }, 300);
    sidebarVisible = false;
    return;
  }

  if (existingSidebar) {
    existingSidebar.remove();
  }

  const container = document.createElement('div');
  container.id = 'phantasm-sidebar-container';
  container.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 360px;
    height: 100vh;
    z-index: 10000;
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.4);
    transition: transform 0.3s ease;
    transform: translateX(100%);
  `;

  const iframe = document.createElement('iframe');
  iframe.id = 'phantasm-sidebar-iframe';
  iframe.src = chrome.runtime.getURL('popup/sidebar.html');
  iframe.style.cssText = `
    width: 100%;
    height: 100%;
    border: none;
  `;

  iframe.addEventListener('load', () => {
    iframe.contentWindow?.postMessage(
      { type: 'ANALYSIS_RESULT', payload: result },
      '*'
    );
  });

  container.appendChild(iframe);
  document.body.appendChild(container);

  requestAnimationFrame(() => {
    container.style.transform = 'translateX(0)';
  });

  sidebarVisible = true;

  window.addEventListener('message', (event) => {
    if (event.data?.type === 'CLOSE_SIDEBAR') {
      container.style.transform = 'translateX(100%)';
      setTimeout(() => {
        container.remove();
      }, 300);
      sidebarVisible = false;
    }
  });
}

function showLoadingBadge(): void {
  try {
    const existing = document.getElementById('phantasm-badge');
    if (existing) existing.remove();

    const badge = document.createElement('div');
    badge.id = 'phantasm-badge';
    badge.style.cssText = `
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      user-select: none;
    `;

    const circle = document.createElement('div');
    circle.id = 'phantasm-badge-circle';
    circle.style.cssText = `
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background-color: #6b7280;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      animation: phantasm-pulse 1.5s ease-in-out infinite;
    `;

    const spinner = document.createElement('div');
    spinner.id = 'phantasm-badge-score';
    spinner.textContent = '...';
    spinner.style.cssText = `
      color: #ffffff;
      font-size: 16px;
      font-weight: 700;
    `;
    circle.appendChild(spinner);

    const label = document.createElement('div');
    label.id = 'phantasm-badge-label';
    label.textContent = 'SCANNING';
    label.style.cssText = `
      color: #6b7280;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 1px;
    `;

    const style = document.createElement('style');
    style.textContent = `
      @keyframes phantasm-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
      }
    `;

    badge.appendChild(circle);
    badge.appendChild(label);
    document.head.appendChild(style);
    document.body.appendChild(badge);
  } catch (err) {
    // Silently fail
  }
}

function sendForAnalysis(metadata: JobMetadata): void {
  console.log('[Phantasm] Sending for analysis:', metadata.title, '—', metadata.company);

  showLoadingBadge();

  chrome.runtime.sendMessage(
    { type: 'ANALYZE_JOB', payload: metadata },
    () => {
      if (chrome.runtime.lastError) {
        console.warn('[Phantasm] sendMessage error:', chrome.runtime.lastError.message);
      }
    }
  );
}

function attemptExtraction(retryCount: number): void {
  const metadata = extractJobMetadata();

  console.log(`[Phantasm] Extraction attempt ${retryCount + 1}: title="${metadata.title}", company="${metadata.company}"`);

  if (metadata.title || metadata.company) {
    sendForAnalysis(metadata);
    return;
  }

  // If we still have retries and the page has meaningful text, try with what we have
  if (retryCount >= 4) {
    // Last resort: send with whatever we have if there's page content
    if (metadata.rawText.length > 200) {
      console.log('[Phantasm] No title/company found after retries, sending with raw text only');
      metadata.title = document.title || 'Unknown';
      sendForAnalysis(metadata);
    } else {
      console.log('[Phantasm] No usable job content found after retries');
    }
    return;
  }

  // Exponential backoff: 1s, 2s, 3s, 4s, 5s
  const delay = (retryCount + 1) * 1000;
  console.log(`[Phantasm] Retrying in ${delay}ms...`);
  setTimeout(() => attemptExtraction(retryCount + 1), delay);
}

function main(): void {
  console.log('[Phantasm] Content script loaded on:', window.location.href);

  // Register message listener immediately
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'ANALYSIS_RESULT') {
      console.log('[Phantasm] Received analysis result:', message.payload.ghostScore);
      injectGhostMeter(message.payload as AnalysisResult);
    }
  });

  // Start extraction with retry
  attemptExtraction(0);
}

// Also re-trigger on LinkedIn SPA navigation (URL changes without full reload)
let lastUrl = window.location.href;
const observer = new MutationObserver(() => {
  if (window.location.href !== lastUrl) {
    lastUrl = window.location.href;
    console.log('[Phantasm] SPA navigation detected:', lastUrl);
    // Remove old badge
    const oldBadge = document.getElementById('phantasm-badge');
    if (oldBadge) oldBadge.remove();
    const oldSidebar = document.getElementById('phantasm-sidebar-container');
    if (oldSidebar) oldSidebar.remove();
    sidebarVisible = false;
    // Re-extract after a short delay for new content to load
    setTimeout(() => attemptExtraction(0), 1500);
  }
});
observer.observe(document.body, { childList: true, subtree: true });

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
