# API Layer

## Overview

The API layer is the HTTP interface of Ledger. It is built with **FastAPI** and exposes all operations the frontend (or any external client) can perform: uploading documents, triggering analysis, polling for results, listing filings, deleting records, and running cross-document comparisons.

---

## Entry Point

**File:** `backend/app/main.py`

FastAPI application is instantiated here. On startup:
- Database tables are initialized via `init_db()`
- Stale rows (`status = "uploaded"` or `"processing"`) are reset to `"failed"` to handle interrupted restarts

CORS middleware is configured to allow all origins (`*`), making local dev and containerized deployments work without extra config.

---

## Routers

### `backend/app/api/contracts.py`

Handles all single-document operations.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/contracts` | Upload a PDF or DOCX file; saves to disk, creates a `Contract` DB row with `status = uploaded` |
| `POST` | `/contracts/{id}/analyze` | Spawns a background task (`run_financial_analysis`) for the given document |
| `GET` | `/contracts/{id}` | Returns current status, live progress, and (when done) the full analysis JSON |
| `GET` | `/contracts` | Lists all uploaded documents with lightweight metadata |
| `DELETE` | `/contracts/{id}` | Removes the DB row and the file from disk |

**Background task flow:**
```
POST /contracts/{id}/analyze
  → FastAPI BackgroundTasks.add_task(run_financial_analysis, id)
  → returns 200 immediately
  → background: pipeline runs, progress updated in-process
  → GET /contracts/{id} polls status + progress
```

### `backend/app/api/compare.py`

Handles multi-document operations.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/benchmark` | Accepts a list of `contract_ids` and optional `metric_names`; calls benchmark pipeline; returns metric grid + LLM commentary |
| `POST` | `/compare/risk` | Accepts `prior_id` and `current_id`; diffs risk factors across two filings; returns delta list |

---

## Request / Response Models

FastAPI uses **Pydantic** for automatic request validation and response serialization.

- `UploadResponse` — `{id, filename, status}`
- `ContractDetail` — `{id, filename, status, error, analysis, progress}`
- `ContractSummary` — `{id, filename, status, company, period, doc_type}`
- `BenchmarkRequest` — `{contract_ids: list[int], metric_names?: list[str]}`
- `RiskCompareRequest` — `{prior_id: int, current_id: int}`

---

## CORS Configuration

Configured in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In production this should be tightened to the frontend origin.

---

## Error Handling

- Missing document → `404 Not Found`
- Unsupported file format → `400 Bad Request`
- Analysis already running → guarded by status check
- Each pipeline stage wrapped in try-catch; failures set `status = "failed"` with an error message stored in `Contract.error`

---

## Key Dependencies

- `fastapi` — routing, dependency injection, background tasks
- `python-multipart` — multipart file upload support
- `sqlmodel` — ORM session injection via `Depends(get_session)`
- `app.pipeline.runner` — analysis orchestrator invoked by background task
- `app.db.models` — `Contract` DB model
