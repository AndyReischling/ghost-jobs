# 👻 Phantasm – Ghost Job Detector

Detects ghost job postings in real-time. Injects a color-coded Ghost Score badge into LinkedIn, Indeed, Greenhouse, and Lever job pages.

## How It Works

1. You open a job posting
2. The extension scrapes visible metadata and sends it to the local Phantasm API
3. The API runs three checks in parallel:
   - **Parity Check** – Is this job actually listed on the company's real careers page?
   - **Financial Health** – Any recent layoffs or hiring freezes in the news?
   - **JD Analysis** – Is this a real, custom-written role or a recycled template?
4. A Ghost Score (0–100) is calculated and a badge is injected on the page

## Ghost Score Legend

| Score | Label | Meaning |
|-------|-------|---------|
| 0–39 | 🟢 Safe | Likely a real, active posting |
| 40–69 | 🟡 Suspicious | Some red flags — proceed with caution |
| 70–100 | 🔴 Ghost | High probability this role will not be filled |

## Quickstart

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and NEWS_API_KEY in .env
uvicorn app.main:app --reload --port 8000
```

### Extension

```bash
cd extension
npm install
npm run build
```

Load `extension/dist/` as an unpacked extension:
- Open `chrome://extensions`
- Enable Developer Mode
- Click "Load unpacked" → select `extension/dist/`

### API Keys Required

- **Anthropic API Key** — [console.anthropic.com](https://console.anthropic.com)
- **NewsAPI Key** — [newsapi.org](https://newsapi.org) (free tier supports 100 req/day)

## Testing the Backend

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.linkedin.com/jobs/view/123456",
    "metadata": {
      "url": "https://www.linkedin.com/jobs/view/123456",
      "title": "Senior Software Engineer",
      "company": "Acme Corp",
      "postedDate": "2024-01-01T00:00:00Z",
      "rawText": "We are looking for a passionate engineer to join our dynamic team...",
      "platform": "linkedin"
    }
  }'
```

## Project Structure

```
phantasm/
├── extension/                 # Chrome Extension (Manifest V3)
│   ├── manifest.json
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── public/icons/          # Extension icons (16, 48, 128px)
│   └── src/
│       ├── shared/            # Shared types and storage helpers
│       ├── content/           # Content script + sidebar component
│       ├── background/        # Service worker
│       └── popup/             # Popup dashboard
├── backend/                   # Python FastAPI backend
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py            # FastAPI app entry point
│       ├── schemas.py         # Pydantic models
│       ├── routers/           # API route handlers
│       ├── services/          # External service integrations
│       └── scoring/           # Ghost score calculation engine
└── README.md
```

## Tech Stack

- **Extension**: TypeScript, React 18, Vite, Chrome Manifest V3
- **Backend**: Python, FastAPI, Pydantic v2
- **Services**: Anthropic Claude (JD analysis), NewsAPI (financial health), Playwright (parity check)
