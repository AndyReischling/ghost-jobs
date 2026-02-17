import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { AnalysisResult, RedFlag, Severity } from '../shared/types';

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

function getScoreLabelText(label: string): string {
  const map: Record<string, string> = {
    ghost: 'LIKELY GHOST',
    suspicious: 'SUSPICIOUS',
    safe: 'SAFE',
  };
  return map[label] ?? label.toUpperCase();
}

function getSeverityColor(severity: Severity): string {
  const map: Record<Severity, string> = {
    low: '#6b7280',
    medium: COLORS.yellow,
    high: COLORS.red,
  };
  return map[severity];
}

function getFlagLabel(type: string): string {
  const map: Record<string, string> = {
    age: 'Age',
    parity: 'Parity',
    sentiment: 'Sentiment',
    financial: 'Financial',
  };
  return map[type] ?? type;
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

interface ScoreGaugeProps {
  score: number;
  color: string;
}

function ScoreGauge({ score, color }: ScoreGaugeProps): React.ReactElement {
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const strokeColor = getScoreColor(color);

  return (
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle
        cx="80"
        cy="80"
        r={radius}
        fill="none"
        stroke={COLORS.border}
        strokeWidth="10"
      />
      <circle
        cx="80"
        cy="80"
        r={radius}
        fill="none"
        stroke={strokeColor}
        strokeWidth="10"
        strokeDasharray={`${progress} ${circumference - progress}`}
        strokeDashoffset={circumference / 4}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.6s ease' }}
      />
      <text
        x="80"
        y="80"
        textAnchor="middle"
        dominantBaseline="central"
        fill={COLORS.text}
        fontSize="36"
        fontWeight="700"
        fontFamily="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
      >
        {score}
      </text>
    </svg>
  );
}

interface RedFlagCardProps {
  flag: RedFlag;
}

function RedFlagCard({ flag }: RedFlagCardProps): React.ReactElement {
  const severityColor = getSeverityColor(flag.severity);

  return (
    <div
      style={{
        backgroundColor: COLORS.card,
        border: `1px solid ${COLORS.border}`,
        borderRadius: '8px',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span style={{ fontSize: '14px' }}>🚩</span>
          <span
            style={{
              color: COLORS.text,
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            {getFlagLabel(flag.type)}
          </span>
        </div>
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            color: severityColor,
            backgroundColor: `${severityColor}20`,
            padding: '2px 8px',
            borderRadius: '9999px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {flag.severity}
        </span>
      </div>
      <p
        style={{
          color: COLORS.subtext,
          fontSize: '12px',
          margin: 0,
          lineHeight: '1.4',
        }}
      >
        {flag.message}
      </p>
    </div>
  );
}

interface SidebarProps {
  result: AnalysisResult | null;
  loading: boolean;
}

function Sidebar({ result, loading }: SidebarProps): React.ReactElement {
  const handleClose = (): void => {
    window.parent.postMessage({ type: 'CLOSE_SIDEBAR' }, '*');
  };

  if (loading) {
    return (
      <div
        style={{
          backgroundColor: COLORS.bg,
          color: COLORS.text,
          height: '100vh',
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          overflow: 'auto',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: `1px solid ${COLORS.border}`,
          }}
        >
          <span style={{ fontSize: '16px', fontWeight: 700 }}>
            👻 Phantasm
          </span>
          <button
            onClick={handleClose}
            style={{
              background: 'none',
              border: 'none',
              color: COLORS.subtext,
              fontSize: '20px',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            ×
          </button>
        </div>
        <div style={{ padding: '32px 20px', textAlign: 'center' }}>
          <div
            style={{
              width: '160px',
              height: '160px',
              borderRadius: '50%',
              backgroundColor: COLORS.card,
              margin: '0 auto 20px',
              animation: 'phantasm-skeleton-pulse 1.5s ease-in-out infinite',
            }}
          />
          <div
            style={{
              width: '120px',
              height: '20px',
              backgroundColor: COLORS.card,
              borderRadius: '4px',
              margin: '0 auto 12px',
              animation: 'phantasm-skeleton-pulse 1.5s ease-in-out infinite',
            }}
          />
          <div
            style={{
              width: '180px',
              height: '14px',
              backgroundColor: COLORS.card,
              borderRadius: '4px',
              margin: '0 auto',
              animation: 'phantasm-skeleton-pulse 1.5s ease-in-out infinite',
            }}
          />
          <div style={{ marginTop: '32px', display: 'flex', flexDirection: 'column', gap: '10px', padding: '0 4px' }}>
            {[1, 2].map((i) => (
              <div
                key={i}
                style={{
                  height: '72px',
                  backgroundColor: COLORS.card,
                  borderRadius: '8px',
                  animation: 'phantasm-skeleton-pulse 1.5s ease-in-out infinite',
                }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div
        style={{
          backgroundColor: COLORS.bg,
          color: COLORS.text,
          height: '100vh',
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: `1px solid ${COLORS.border}`,
          }}
        >
          <span style={{ fontSize: '16px', fontWeight: 700 }}>
            👻 Phantasm
          </span>
          <button
            onClick={handleClose}
            style={{
              background: 'none',
              border: 'none',
              color: COLORS.subtext,
              fontSize: '20px',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            ×
          </button>
        </div>
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            color: COLORS.subtext,
          }}
        >
          <span style={{ fontSize: '48px' }}>👻</span>
          <p style={{ margin: 0, fontSize: '14px' }}>
            No scan data yet. Visit a job posting.
          </p>
        </div>
      </div>
    );
  }

  const scoreColor = getScoreColor(result.ghostScore.color);
  const labelText = getScoreLabelText(result.ghostScore.label);

  return (
    <div
      style={{
        backgroundColor: COLORS.bg,
        color: COLORS.text,
        height: '100vh',
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        display: 'flex',
        flexDirection: 'column',
        overflow: 'auto',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 20px',
          borderBottom: `1px solid ${COLORS.border}`,
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: '16px', fontWeight: 700 }}>👻 Phantasm</span>
        <button
          onClick={handleClose}
          style={{
            background: 'none',
            border: 'none',
            color: COLORS.subtext,
            fontSize: '20px',
            cursor: 'pointer',
            padding: '4px',
          }}
        >
          ×
        </button>
      </div>

      {/* Score Section */}
      <div
        style={{
          textAlign: 'center',
          padding: '24px 20px 16px',
          flexShrink: 0,
        }}
      >
        <ScoreGauge
          score={result.ghostScore.score}
          color={result.ghostScore.color}
        />
        <div
          style={{
            color: scoreColor,
            fontSize: '14px',
            fontWeight: 700,
            letterSpacing: '2px',
            marginTop: '8px',
          }}
        >
          {labelText}
        </div>
        <div
          style={{
            color: COLORS.subtext,
            fontSize: '13px',
            marginTop: '8px',
            lineHeight: '1.4',
          }}
        >
          <div style={{ fontWeight: 500, color: COLORS.text }}>
            {result.jobTitle}
          </div>
          <div>{result.companyName}</div>
        </div>
      </div>

      {/* Red Flags */}
      {result.redFlags.length > 0 && (
        <div style={{ padding: '0 20px 20px', flex: 1 }}>
          <h3
            style={{
              fontSize: '12px',
              color: COLORS.subtext,
              textTransform: 'uppercase',
              letterSpacing: '1px',
              marginBottom: '10px',
              fontWeight: 600,
            }}
          >
            Red Flags
          </h3>
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}
          >
            {result.redFlags.map((flag, index) => (
              <RedFlagCard key={index} flag={flag} />
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: `1px solid ${COLORS.border}`,
          textAlign: 'center',
          flexShrink: 0,
        }}
      >
        <span style={{ color: COLORS.subtext, fontSize: '11px' }}>
          Scanned via Phantasm · {relativeTime(result.analyzedAt)}
        </span>
      </div>
    </div>
  );
}

function SidebarApp(): React.ReactElement {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const handleMessage = (event: MessageEvent): void => {
      if (event.data?.type === 'ANALYSIS_RESULT') {
        setResult(event.data.payload as AnalysisResult);
        setLoading(false);
      }
    };

    window.addEventListener('message', handleMessage);

    const timeout = setTimeout(() => {
      setLoading(false);
    }, 10000);

    return () => {
      window.removeEventListener('message', handleMessage);
      clearTimeout(timeout);
    };
  }, []);

  return <Sidebar result={result} loading={loading} />;
}

const rootEl = document.getElementById('root');
if (rootEl) {
  const root = ReactDOM.createRoot(rootEl);
  root.render(<SidebarApp />);
}
