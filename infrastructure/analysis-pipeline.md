# Analysis Pipeline

## Overview

The analysis pipeline is the core intelligence engine of Ledger. It takes a parsed document's full text and runs it through a sequence of six specialized LLM-powered stages, each extracting a different class of financial insight. The pipeline is orchestrated by a single runner, with each stage independently fault-tolerant.

---

## Module Location

`backend/app/pipeline/`

```
pipeline/
├── runner.py        # Orchestrator — runs all stages in sequence
├── progress.py      # Thread-safe in-process progress store
├── identity.py      # Stage 1: document identity extraction
├── metrics.py       # Stage 2: financial metrics extraction
├── tone.py          # Stage 3: management tone analysis
├── risk_factors.py  # Stage 4: risk factor extraction
├── memo.py          # Stage 5: investment memo generation
└── benchmark.py     # Stage 6 (separate): cross-document comparison
```

---

## Pipeline Stages

### Stage 1 — Identity (`identity.py`)

**Input:** full document text  
**Output:** `DocumentIdentity`

Extracts:
- `company` — company name
- `period` — reporting period (e.g., "Q3 2024", "FY2023")
- `doc_type` — document type (`10-K`, `10-Q`, `earnings_release`, `transcript`)

Used downstream to label all analysis outputs and display in the UI library.

---

### Stage 2 — Metrics (`metrics.py`)

**Input:** full document text  
**Output:** `MetricSet` (list of `Metric`)

Extracts the 12 canonical financial metrics:

| Metric Key | Label |
|------------|-------|
| `revenue` | Revenue |
| `gross_margin` | Gross Margin |
| `operating_income` | Operating Income |
| `operating_margin` | Operating Margin |
| `net_income` | Net Income |
| `eps` | EPS |
| `ebitda` | EBITDA |
| `free_cash_flow` | Free Cash Flow |
| `capex` | CapEx |
| `total_debt` | Total Debt |
| `cash_and_equivalents` | Cash & Equivalents |
| `guidance_revenue` | Revenue Guidance |

Each `Metric` record includes:
- `name` — canonical key
- `label` — display name
- `period` — which reporting period this value covers
- `value` — formatted string (e.g., "$12.3B")
- `value_numeric` — float for calculations and comparisons
- `unit` — `USD_millions`, `USD_billions`, `percent`, etc.
- `basis` — `GAAP` or `non-GAAP`
- `source` — verbatim excerpt from the document

---

### Stage 3 — Tone Analysis (`tone.py`)

**Input:** full document text  
**Output:** `ToneAnalysis`

Analyzes management language in the document:
- `sentiment` — overall tone: `positive`, `neutral`, or `negative`
- `confidence` — level of management confidence: `high`, `medium`, `low`
- `hedging` — frequency of hedging language: `high`, `medium`, `low`
- `key_passages` — list of `TonePassage` (verbatim quote + explanation of its significance)

Used in the `ToneGauge` UI component to display visual sentiment indicators.

---

### Stage 4 — Risk Factors (`risk_factors.py`)

**Input:** full document text  
**Output:** `RiskFactorSet` (list of `RiskFactor`)

Extracts disclosed risks from the document. Each `RiskFactor` includes:
- `category` — e.g., `market`, `regulatory`, `operational`, `financial`, `macroeconomic`
- `title` — short name of the risk
- `description` — full explanation
- `severity` — `high`, `medium`, or `low`

Also supports **risk comparison** (`RiskComparison`) between two filings (prior vs. current), identifying new risks, removed risks, and escalated/de-escalated risks.

---

### Stage 5 — Investment Memo (`memo.py`)

**Input:** full document text + prior stage outputs  
**Output:** `InvestmentMemo`

Generates a structured analyst-style memo:
- `overview` — company and period summary paragraph
- `bull_case` — list of bullish investment arguments
- `bear_case` — list of bearish investment arguments
- `key_risks` — top risks to the investment thesis
- `questions_for_management` — suggested follow-up questions for earnings calls

Displayed on the `/memo` frontend page.

---

### Stage 6 — Benchmark (`benchmark.py`)

**Input:** list of `FinancialAnalysis` objects (from ≥2 documents)  
**Output:** metrics grid + `BenchmarkCommentary`

Cross-document comparison:
- Builds a grid of the selected metrics across all provided filings
- Sends the grid to the LLM for narrative commentary (highlights, outliers, trends)

Triggered separately via `POST /benchmark`, not as part of the single-document pipeline.

---

## Orchestrator

**File:** `runner.py`

`run_financial_analysis(contract_id)` is the background task entry point:

```
1. Load Contract from DB
2. Set status = "processing"
3. Parse document (ingestion router)
4. Structure document (chunked map-reduce → outline)
5. Run Stage 1: identity
6. Run Stage 2: metrics
7. Run Stage 3: tone
8. Run Stage 4: risk_factors
9. Run Stage 5: memo
10. Assemble FinancialAnalysis object
11. Serialize to JSON, save to Contract.analysis
12. Set status = "done"
```

Each stage (3–9) is wrapped in a try-except block. If a stage fails, the error is logged and the pipeline continues with `None` for that field — the frontend handles missing fields gracefully.

---

## Progress Tracking

**File:** `progress.py`

An **in-process, thread-safe dictionary** keyed by `contract_id`. Updated at each pipeline stage transition by the background task. Polled by `GET /contracts/{id}` every time the frontend requests the status.

```python
# Structure
{
  contract_id: {
    "stage": "metrics",
    "chunk": 3,
    "total_chunks": 12,
    "message": "Extracting financial metrics..."
  }
}
```

**Important constraint:** Because this store is in-process memory, the backend must run as a **single instance**. Horizontal scaling would require migrating progress to Redis or a DB table.

---

## Graceful Degradation

Each stage is independently fault-tolerant:
- Stage failure → logs error, stores `None` for that field
- One bad stage does not abort the remaining stages
- Frontend checks for `null` fields and renders placeholder UI

---

## Key Dependencies

- `app.llm.client` — `GeminiClient` for all LLM calls
- `app.llm.prompts` — prompt templates for each stage
- `app.schemas.financial` — output types for each stage
- `app.ingestion.router` — document parsing entry point
- `app.db.models` — `Contract` DB model for status updates
