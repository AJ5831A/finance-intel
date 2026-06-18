# Ledger: AI Financial Document Analyst

Read a filing the way an analyst would, in seconds. Upload a 10-K, 10-Q, earnings release, or call transcript, and Ledger ingests and structures it, extracts the financial metrics with period-over-period comparison, reads management's tone, pulls and categorises risk factors, benchmarks companies against one another, and drafts an investment memo. The judgment is left to you.

**Stack.** Backend: FastAPI, Google Gemini (`google-genai` with structured output), and SQLite (via SQLModel). Frontend: React, Vite, TypeScript, and Tailwind. Parsing: pdfplumber for PDF and python-docx for DOCX, with a Docling fallback for scanned PDFs.

**Capabilities.** Each capability below maps to a graded success metric:

| Capability | What it does |
|---|---|
| Metric extraction | Extracts named figures (revenue, margins, EPS, cash flow, debt, guidance…) into a table with YoY/QoQ change |
| Management tone | Scores sentiment, confidence, and hedging; surfaces the most confident and most cautious passages |
| Risk factors | Extracts and categorises disclosed risks; diffs two periods to flag **new** / **escalated** risks |
| Competitor benchmarking | Side-by-side metric grid across companies, with comparative commentary |
| Investment memo | Company overview, financial summary, bull case, bear case, key risks, and open questions, all grounded in the extracted data |

---

## Architecture

Document parsing feeds a single best-effort analysis pipeline. The result is stored as one JSON blob and rendered by the frontend, and cross-document features read those stored results.

```
            ┌──────────────── ingestion ────────────────┐
 PDF / DOCX ─► pdfplumber / python-docx ─► Docling fallback ─► full text
                (scanned PDF, <30 chars of text layer)              │
                                                                    ▼
   ┌──────────── run_financial_analysis  (FastAPI background task) ────────────┐
   │  1. structure   chunk → map: blocks per chunk → merge → synthesize outline │ ← streams per-chunk progress
   │  2. identity    company · period · doc-type                                 │
   │  3. metrics     chunked extract → dedupe by (canonical name, period)        │  ▶ metric extraction
   │  4. tone        overall sentiment + confidence + telling passages           │  ▶ tone analysis
   │  5. risk        chunked extract → dedupe risk factors                        │  ▶ risk extraction
   │  6. memo        synthesise from (metrics + tone + risks)                     │  ▶ investment memo
   └────────────────────────────────────────────────────────────────────────────┘
                                      │
                  FinancialAnalysis JSON ─► SQLite (Contract.analysis)
                                      │
   Cross-document:  POST /benchmark      companies × metrics grid + commentary
                    POST /compare/risk   period-over-period risk-factor diff
```

**Key design points**

- **Chunked map-reduce structuring.** A large filing cannot be structured in one LLM call, because the JSON response truncates against the output-token budget. `ingestion/structure.py` splits the text (`ingestion/chunking.py`), parses each chunk into ordered blocks (the map step), merges and de-duplicates the overlap in code, then makes one bounded call over the headings alone to synthesize a clean title and outline (the reduce step). This is the stage that streams the live chunk-progress animation.
- **Schema sanitizer.** Gemini's `response_schema` rejects JSON Schema that Pydantic normally emits: `default` keys, `$ref` and `$defs` indirection, recursive schemas, and `anyOf` null unions. `llm/schema.py:to_gemini_schema` rewrites any Pydantic model into a Gemini-safe schema, and `llm/client.py` parses the response back into the typed model. Every structured call goes through it.
- **Best-effort stages.** Each pipeline stage is wrapped so that one failure, such as a bad chunk or a flaky call, degrades gracefully instead of sinking the whole analysis.
- **Ephemeral progress.** `pipeline/progress.py` is a thread-safe, in-process store that the running background task updates and `GET /contracts/{id}` reads, and it drives the frontend animation. It is in-process by design, matching the single-worker development setup.
- **Resilient startup.** On boot, any row left in `processing` or `uploaded` by a restart is marked `failed`, so a reload never leaves a stuck "zombie" analysis.

### Backend modules

```
backend/app/
├── ingestion/    pdf.py · docx.py · docling_parser.py · router.py · chunking.py · structure.py
├── pipeline/     identity.py · metrics.py · tone.py · risk_factors.py · memo.py
│                 benchmark.py · runner.py · progress.py
├── llm/          client.py · schema.py (sanitizer) · prompts.py
├── schemas/      models.py (document structure) · financial.py (analysis models)
├── api/          contracts.py (upload/analyze/get/list/delete) · compare.py (benchmark, risk diff)
├── db/           engine.py · models.py (Contract)
├── config.py     settings (env)
└── main.py       app factory, CORS, startup recovery
```

### Frontend

```
frontend/src/
├── pages/        Library (filings) · Analysis (dashboard) · Document · Memo · Benchmark
├── components/   Shell · ChunkProgress · MetricsTable · ToneGauge
├── lib/          finance.ts (labels, colours, stage map)
└── api/client.ts
```

### HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/contracts` | Upload a filing (multipart) and return its id |
| `POST` | `/contracts/{id}/analyze` | Start analysis as a background task |
| `GET`  | `/contracts/{id}` | Return status, the live `progress`, and the `analysis` JSON |
| `GET`  | `/contracts` | List filings with id, company, period, doc_type, and status |
| `DELETE` | `/contracts/{id}` | Remove a filing |
| `POST` | `/benchmark` | Given `{contract_ids[]}`, return the metric grid and highlights |
| `POST` | `/compare/risk` | Given `{prior_id, current_id}`, return the risk-factor deltas |

---

## Workflow

End-to-end flow for analysing a single filing and then comparing across filings:

```
Browser (React)                    FastAPI                         Gemini · SQLite
──────────────                     ───────                         ───────────────
 choose file ──── POST /contracts ──────► save file + row(uploaded) ──────► SQLite
 (auto)     ──── POST /contracts/{id}/analyze ─► spawn background task: run_financial_analysis
 navigate to /contracts/{id}
 poll 2s   ──── GET /contracts/{id} ────► { status, progress, analysis }   ◄── progress store
    │  status = processing → <ChunkProgress> shows the current stage and,
    │                         during structuring, each parsed chunk rising in
    │  status = done       → render from analysis JSON:
    │                         · Dashboard  → metrics table + tone gauge + risk factors
    │                         · Memo       → overview / bull / bear / risks / questions
    │                         · Document   → synthesized outline + typeset body
 Benchmark page
   pick ≥2 filings ─ POST /benchmark ─────► grid assembled from each filing's stored metrics
                                            + one LLM call for comparative commentary
   pick prior+current ─ POST /compare/risk ► LLM diffs the two stored risk-factor sets
```

The analysis stages run **sequentially inside the background task**, so a large 10-K takes a few minutes, since each chunk is a real Gemini call, while short earnings releases finish quickly. The UI keeps polling and updates live throughout.

---

## Prerequisites

- **Python 3.13.** A virtualenv `legalvenv/` is already created at the repo root.
- **Node 20.** Required for the React frontend.
- **Google Gemini API key.** The free tier is sufficient for development.

## Setup

```bash
# 1. Backend dependencies
legalvenv/bin/pip install -r backend/requirements.txt

# 2. Configure the API key
cp backend/.env.example backend/.env
#    then set GEMINI_API_KEY in backend/.env  (GEMINI_MODEL defaults to gemini-2.5-flash)

# 3. Frontend dependencies
cd frontend && npm install
```

## Running

```bash
# Backend  → http://localhost:8000  (docs at /docs)
cd backend && ../legalvenv/bin/uvicorn app.main:app --reload

# Frontend → http://localhost:5173
cd frontend && npm run dev
```

CORS is open, so the frontend works on whatever port Vite picks.

## Usage

1. Open the frontend and go to **Filings**.
2. **Analyse a filing.** Upload a PDF or DOCX. You are taken straight to the dashboard, which shows the live multi-stage progress, including the chunk animation during structuring.
3. **Review the results** when analysis completes: the **Dashboard** (metrics table, tone gauge, and risk factors), plus the **Investment memo** and **Document** views.
4. **Benchmark.** On the Benchmark tab, select two or more analysed filings for the metric comparison grid, or pick a prior and a current filing to diff their risk factors.

## Testing

```bash
cd backend && ../legalvenv/bin/pytest        # unit tests; Gemini is mocked, no API key needed
```

> Note: `eval/` and `fixtures/` are leftovers from the contract-analysis prototype this project was built on and are not wired to the current pipeline.

## Deployment

Ledger is a stateful, single-instance app (in-process progress, background tasks, SQLite, and local uploads), so it deploys as **one backend process with a persistent disk** alongside a static frontend. Docker artifacts (`backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml`) and a slim `backend/requirements-prod.txt` are included. Full instructions, covering single-host Docker, the managed split (Vercel with Render or Fly), TLS, and the scaling constraints, are in **[DEPLOYMENT.md](DEPLOYMENT.md)**.

```bash
GEMINI_API_KEY=your-key VITE_API_BASE=http://localhost:8000 docker compose up -d --build
# frontend → http://localhost:8080   backend → http://localhost:8000
```

---

## Document parsing & the Docling fallback

- **PDF.** pdfplumber extracts text page by page.
- **DOCX.** python-docx extracts paragraph text.
- **Scanned-PDF fallback.** If the text layer yields fewer than roughly 30 characters, the ingestion router retries with Docling, which handles OCR and complex layouts. Docling is an optional heavy dependency, and a clear error is raised if it is not installed.
