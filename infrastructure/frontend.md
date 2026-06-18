# Frontend

## Overview

The Ledger frontend is a React Single Page Application (SPA) built with TypeScript, Vite, and Tailwind CSS. It provides the full user interface for uploading financial documents, monitoring live analysis progress, exploring extracted financial data, reading investment memos, and running cross-document benchmarks.

---

## Technology Stack

| Tool | Version | Role |
|------|---------|------|
| React | 19.2 | UI component framework |
| TypeScript | 6.0 | Type-safe JavaScript |
| Vite | 8.0 | Build tool and dev server |
| Tailwind CSS | 3.4 | Utility-first styling |
| React Router | 7.18 | Client-side SPA routing |

---

## Project Structure

`frontend/src/`

```
src/
├── pages/
│   ├── Library.tsx      # Home screen: document list + upload
│   ├── Analysis.tsx     # Live progress + analysis dashboard
│   ├── Memo.tsx         # Investment memo view
│   ├── Document.tsx     # Structured document outline view
│   └── Benchmark.tsx    # Multi-document comparison
├── components/
│   ├── Shell.tsx        # Layout: nav bar + page outlet
│   ├── Analysis.tsx     # Dashboard container component
│   ├── ChunkProgress.tsx# Live chunk-by-chunk parsing animation
│   ├── MetricsTable.tsx # Financial metrics grid with YoY/QoQ changes
│   └── ToneGauge.tsx    # Visual sentiment/confidence gauge
├── api/
│   └── client.ts        # Fetch wrapper for all backend API calls
├── lib/
│   └── finance.ts       # Domain utilities: metric labels, colors, stage map
├── types.ts             # TypeScript interfaces mirroring backend schemas
├── App.tsx              # React Router setup
└── main.tsx             # React entry point
```

---

## Pages

### Library (`pages/Library.tsx`)

The home screen. Displayed at `/`.

- Lists all uploaded documents in a table with: company, period, doc type, status badge
- File upload widget — accepts PDF and DOCX files
  - On select: calls `uploadDocument()` → then immediately calls `analyzeDocument()`
  - On success: navigates to `/analysis/:id`
- Delete button per row — calls `deleteDocument(id)` and refreshes the list

### Analysis (`pages/Analysis.tsx`)

Displayed at `/analysis/:id`. The primary insight dashboard.

**While processing:**
- Polls `GET /contracts/:id` every 2 seconds
- Displays `ChunkProgress` component with live stage and chunk progress

**When done:**
- Renders the full analysis dashboard:
  - `MetricsTable` — all extracted financial metrics
  - `ToneGauge` — sentiment, confidence, hedging levels + key passages
  - Risk factors list — categorized with severity badges
- Navigation links to Memo and Document pages

### Memo (`pages/Memo.tsx`)

Displayed at `/analysis/:id/memo`.

Renders the `InvestmentMemo` structured output:
- Company overview paragraph
- Bull case arguments (bulleted)
- Bear case arguments (bulleted)
- Key risks (bulleted)
- Suggested questions for management

### Document (`pages/Document.tsx`)

Displayed at `/analysis/:id/document`.

Renders the structured document outline extracted during the ingestion/structuring stage:
- Hierarchical headings and section titles
- Useful for navigating long 10-K filings

### Benchmark (`pages/Benchmark.tsx`)

Displayed at `/benchmark`.

- Multi-select from all uploaded documents (requires ≥2)
- Optional: choose which metrics to compare
- Calls `POST /benchmark` and displays:
  - Metric grid table (companies as columns, metrics as rows)
  - LLM-generated commentary on the comparison
- Optional risk comparison: select prior and current filing → calls `POST /compare/risk`

---

## Components

### Shell (`components/Shell.tsx`)

Top-level layout wrapper. Renders the navigation bar and an `<Outlet />` for page content. All pages are rendered inside the Shell.

### ChunkProgress (`components/ChunkProgress.tsx`)

Animates the document parsing and analysis progress. Displays:
- Current stage name (e.g., "Structuring document", "Extracting metrics")
- Chunk progress bar (chunk N of M)
- Animated status message

Receives live data from the `progress` field in `GET /contracts/:id` response.

### MetricsTable (`components/MetricsTable.tsx`)

Renders the extracted financial metrics as a styled table:
- Metric name and label
- Current period value with unit formatting
- Period-over-period change (colored green/red)
- Basis label (GAAP / non-GAAP)
- Source excerpt on hover or expand

### ToneGauge (`components/ToneGauge.tsx`)

Visual representation of management tone analysis:
- Gauge or badge for `sentiment` (positive / neutral / negative)
- Gauge or badge for `confidence` (high / medium / low)
- Gauge or badge for `hedging` (high / medium / low)
- Expandable list of key passages with explanations

### Analysis (`components/Analysis.tsx`)

Container component that orchestrates the analysis dashboard layout — assembles `MetricsTable`, `ToneGauge`, and risk factors section into the full dashboard view.

---

## API Client

**File:** `api/client.ts`

All backend communication goes through this module. Base URL configured via `VITE_API_BASE` environment variable (falls back to `http://localhost:8000`).

| Function | HTTP Call | Purpose |
|----------|-----------|---------|
| `uploadDocument(file)` | `POST /contracts` | Upload file |
| `analyzeDocument(id)` | `POST /contracts/{id}/analyze` | Trigger analysis |
| `getDocument(id)` | `GET /contracts/{id}` | Poll status + get results |
| `listDocuments()` | `GET /contracts` | Get all documents |
| `deleteDocument(id)` | `DELETE /contracts/{id}` | Delete a document |
| `benchmark(ids, metrics?)` | `POST /benchmark` | Run cross-document comparison |
| `compareRisk(priorId, currentId)` | `POST /compare/risk` | Diff risk factors |

---

## Domain Utilities

**File:** `lib/finance.ts`

- `METRIC_LABELS` — map of canonical metric key → display label
- `METRIC_COLORS` — map of metric key → Tailwind color class for styling
- `STAGE_LABELS` — map of pipeline stage name → user-facing progress message
  - e.g., `"metrics"` → `"Extracting financial metrics..."`

---

## Types

**File:** `types.ts`

TypeScript interfaces mirroring backend Pydantic models:
- `Contract`, `ContractSummary`, `ContractDetail`
- `FinancialAnalysis`, `DocumentIdentity`
- `Metric`, `MetricSet`
- `ToneAnalysis`, `TonePassage`
- `RiskFactor`
- `InvestmentMemo`
- `BenchmarkResult`, `RiskComparison`

---

## Routing

**File:** `App.tsx`

```
/                        → Library (document list + upload)
/analysis/:id            → Analysis (progress + dashboard)
/analysis/:id/memo       → Memo
/analysis/:id/document   → Document outline
/benchmark               → Benchmark comparison
```

All routes are wrapped in `Shell` for consistent layout.

---

## Build & Deployment

- `npm run dev` — Vite dev server (hot reload)
- `npm run build` — Production build to `dist/`
- `npm run typecheck` — TypeScript strict type check
- `VITE_API_BASE` — must be set at **build time** for production (Vite inlines env vars)

In Docker, the frontend is built in a multi-stage Dockerfile and the `dist/` output is served by **Nginx** on port 80.
