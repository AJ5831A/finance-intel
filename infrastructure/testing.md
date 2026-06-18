# Testing & Quality

## Overview

Ledger's test suite uses **pytest** for backend testing. Tests cover API endpoints, database operations, document chunking, and benchmark logic. The Gemini API is mocked in all tests — no real API key is needed to run the suite.

---

## Module Location

`backend/tests/`

```
tests/
├── conftest.py          # Pytest fixtures: mocked Gemini, test DB, test client
├── test_api.py          # API endpoint integration tests
├── test_benchmark.py    # Benchmark pipeline logic tests
├── test_chunking.py     # Document chunking unit tests
└── test_db.py           # Database operation tests
```

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt   # includes pytest and httpx
pytest                             # run all tests
pytest tests/test_api.py          # run a specific file
pytest -v                          # verbose output
pytest -k "test_upload"           # run tests matching a name pattern
```

No `GEMINI_API_KEY` required — the Gemini client is mocked in `conftest.py`.

---

## Test Fixtures

**File:** `conftest.py`

### `mock_gemini`

Patches `app.llm.client.GeminiClient.call` to return pre-defined Pydantic objects instead of calling the real Gemini API.

- Prevents network calls in tests
- Returns deterministic structured output for each pipeline stage
- Allows testing pipeline logic without API costs or rate limits

### `test_db`

Creates a temporary in-memory SQLite database for each test session.

- Overrides the `get_session` dependency
- Automatically torn down after each test
- Ensures tests don't pollute each other or the development database

### `client`

An `httpx.AsyncClient` or `TestClient` pointed at the FastAPI app with test dependencies injected.

- Used by API endpoint tests to make HTTP requests
- Inherits the `test_db` and `mock_gemini` fixtures

---

## Test Files

### `test_api.py` — API Endpoint Tests

Tests the full HTTP layer end-to-end (with mocked Gemini and test DB).

Key scenarios covered:
- `POST /contracts` — successful upload of a PDF file
- `POST /contracts` — rejection of an unsupported file format
- `POST /contracts/{id}/analyze` — successful analysis trigger
- `GET /contracts/{id}` — returns correct status and analysis once done
- `GET /contracts` — lists all uploaded documents
- `DELETE /contracts/{id}` — removes document and file
- `POST /benchmark` — successful benchmark with 2+ documents
- `POST /compare/risk` — successful risk comparison

### `test_benchmark.py` — Benchmark Logic Tests

Tests the `benchmark.py` pipeline stage in isolation.

Key scenarios covered:
- Correct metric grid construction from multiple `FinancialAnalysis` objects
- Handling of missing metrics (when a stage failed for one document)
- LLM commentary generation (mocked)

### `test_chunking.py` — Chunking Unit Tests

Tests `app/ingestion/chunking.py` in isolation — no LLM or DB involved.

Key scenarios covered:
- Short text (under chunk limit) returned as a single chunk
- Long text split into multiple chunks within the size limit
- Chunk boundaries respect paragraph breaks where possible
- Empty text handled without error

### `test_db.py` — Database Tests

Tests `app/db/` operations directly using the test DB fixture.

Key scenarios covered:
- Creating a `Contract` row
- Updating status from `uploaded` → `processing` → `done`
- Storing and retrieving the `analysis` JSON blob
- Startup recovery: stale `processing` rows marked `failed`

---

## Evaluation Suite

`backend/eval/`

Separate from the unit tests — this is a manual/semi-automated evaluation harness for testing LLM output quality against real documents.

- `fixtures/` — sample financial documents (SEC filings, earnings releases)
- Runs the full pipeline on real documents
- Compares extracted metrics against known ground-truth values
- Used for regression testing when prompt templates or the LLM model changes

Not run in CI — requires a real `GEMINI_API_KEY` and real documents.

---

## Dependencies

**File:** `requirements.txt` (development, extends `requirements-prod.txt`)

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support for FastAPI |
| `httpx` | HTTP client for API endpoint testing |
| `reportlab` | PDF generation for test fixture creation |

---

## Quality Checks

### Type Checking

Not currently enforced via CI, but the backend uses Pydantic extensively — type errors surface at runtime through validation failures rather than static analysis.

### Frontend Type Checking

```bash
cd frontend
npm run typecheck    # runs tsc --noEmit with strict mode
```

TypeScript 6.0 with strict checks enabled. All backend response types are mirrored in `types.ts`.

### Linting (Frontend)

```bash
cd frontend
npm run lint    # ESLint with typescript-eslint rules
```

---

## Known Gaps

- No end-to-end browser tests (Playwright/Cypress not set up)
- No CI/CD pipeline configured (GitHub Actions not present)
- Backend has no static type checker (mypy not configured)
- Eval suite requires manual execution and review — no automated pass/fail threshold
