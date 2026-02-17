import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { ScanHistoryEntry } from '../shared/types';
import { getScanHistory, clearHistory } from '../shared/storage';

const COLORS = {
  bg: '#0d0d0d',
  card: '#1a1a1a',
  border: '#2a2a2a',
  green: '#22c55e',
  yellow: '#eab308',
  red: '#ef4444',
  text: '#ffffff',
  subtext: '#a1a1aa',
} as const;

function getScoreColor(color: string): string {
  const map: Record<string, string> = {
    green: COLORS.green,
    yellow: COLORS.yellow,
    red: COLORS.red,
  };
  return map[color] ?? COLORS.subtext;
}

function relativeTime(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '…' : text;
}

function isWithinLastWeek(isoDate: string): boolean {
  const diff = Date.now() - new Date(isoDate).getTime();
  return diff < 7 * 24 * 60 * 60 * 1000;
}

interface StatCardProps {
  label: string;
  value: number;
}

function StatCard({ label, value }: StatCardProps): React.ReactElement {
  return (
    <div
      style={{
        flex: 1,
        backgroundColor: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '8px',
        padding: '12px 8px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: '22px',
          fontWeight: 700,
          color: COLORS.text,
          lineHeight: '1.2',
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: '10px',
          color: COLORS.subtext,
          marginTop: '4px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          fontWeight: 500,
        }}
      >
        {label}
      </div>
    </div>
  );
}

interface HistoryRowProps {
  entry: ScanHistoryEntry;
}

function HistoryRow({ entry }: HistoryRowProps): React.ReactElement {
  const scoreColor = getScoreColor(entry.ghostScore.color);

  const handleClick = (): void => {
    chrome.tabs.create({ url: entry.jobUrl });
  };

  return (
    <div
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 12px',
        backgroundColor: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '8px',
        cursor: 'pointer',
        transition: 'border-color 0.2s',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = COLORS.subtext;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.borderColor = COLORS.border;
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: '12px',
            fontWeight: 600,
            color: COLORS.text,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {truncate(`${entry.companyName} — ${entry.jobTitle}`, 36)}
        </div>
        <div
          style={{
            fontSize: '10px',
            color: COLORS.subtext,
            marginTop: '2px',
          }}
        >
          {relativeTime(entry.analyzedAt)}
        </div>
      </div>
      <div
        style={{
          marginLeft: '10px',
          padding: '3px 8px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 700,
          color: scoreColor,
          backgroundColor: `${scoreColor}20`,
          whiteSpace: 'nowrap',
        }}
      >
        {entry.ghostScore.score} {entry.ghostScore.label.toUpperCase()}
      </div>
    </div>
  );
}

function Popup(): React.ReactElement {
  const [history, setHistory] = useState<ScanHistoryEntry[]>([]);

  useEffect(() => {
    getScanHistory().then(setHistory);
  }, []);

  const totalScanned = history.length;
  const ghostsAvoided = history.filter((e) => e.ghostScore.score >= 70).length;
  const thisWeek = history.filter((e) => isWithinLastWeek(e.analyzedAt)).length;

  const recentEntries = history.slice(0, 10);

  const handleClear = async (): Promise<void> => {
    await clearHistory();
    setHistory([]);
  };

  return (
    <div
      style={{
        width: '400px',
        height: '520px',
        backgroundColor: COLORS.bg,
        color: COLORS.text,
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '20px 20px 12px',
          borderBottom: `1px solid ${COLORS.border}`,
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: '18px', fontWeight: 700 }}>👻 Phantasm</div>
        <div
          style={{
            fontSize: '12px',
            color: COLORS.subtext,
            marginTop: '2px',
          }}
        >
          Ghost Job Detector
        </div>
      </div>

      {/* Stats Bar */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          padding: '14px 20px',
          flexShrink: 0,
        }}
      >
        <StatCard label="Jobs Scanned" value={totalScanned} />
        <StatCard label="Ghosts Avoided" value={ghostsAvoided} />
        <StatCard label="This Week" value={thisWeek} />
      </div>

      {/* Scan History */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          padding: '0 20px',
        }}
      >
        {recentEntries.length > 0 ? (
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}
          >
            {recentEntries.map((entry) => (
              <HistoryRow key={entry.id} entry={entry} />
            ))}
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              gap: '10px',
              color: COLORS.subtext,
            }}
          >
            <span style={{ fontSize: '40px' }}>👻</span>
            <p style={{ fontSize: '13px', margin: 0, textAlign: 'center' }}>
              No scans yet. Visit a job posting to get started.
            </p>
          </div>
        )}
      </div>

      {/* Footer */}
      {history.length > 0 && (
        <div
          style={{
            padding: '10px 20px',
            borderTop: `1px solid ${COLORS.border}`,
            textAlign: 'center',
            flexShrink: 0,
          }}
        >
          <button
            onClick={handleClear}
            style={{
              background: 'none',
              border: 'none',
              color: COLORS.subtext,
              fontSize: '11px',
              cursor: 'pointer',
              textDecoration: 'underline',
              padding: '4px',
            }}
          >
            Clear history
          </button>
        </div>
      )}
    </div>
  );
}

const rootEl = document.getElementById('root');
if (rootEl) {
  const root = ReactDOM.createRoot(rootEl);
  root.render(<Popup />);
}
