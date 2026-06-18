# Data Persistence

## Overview

Ledger uses **SQLite** as its database, managed via **SQLModel** (a library combining SQLAlchemy and Pydantic). There is a single table — `Contract` — that stores document metadata, processing status, and the full serialized analysis result. The design is intentionally simple: one persistent file on disk, zero external database dependencies.

---

## Module Location

`backend/app/db/`

```
db/
├── engine.py    # SQLite engine factory, session dependency, init_db()
└── models.py    # Contract SQLModel table definition
```

---

## Database Engine

**File:** `engine.py`

### Engine Setup

```python
engine = create_engine(settings.db_path, connect_args={"check_same_thread": False})
```

- `db_path` defaults to `contracts.db` in the working directory (configurable via `DB_PATH` env var)
- `check_same_thread=False` is required because FastAPI serves requests on multiple threads while SQLite defaults to single-thread access

### Session Dependency

```python
def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

Injected into API route handlers via FastAPI's `Depends(get_session)`. Each request gets its own session, automatically committed and closed.

### Database Initialization

```python
def init_db():
    SQLModel.metadata.create_all(engine)
```

Called on application startup (`main.py`). Creates all tables if they don't exist. Safe to call on every startup — no-ops if tables already exist.

---

## Data Model

**File:** `models.py`

### Contract Table

```python
class Contract(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    format: str                    # "pdf" or "docx"
    status: str                    # "uploaded" | "processing" | "done" | "failed"
    error: str | None = None       # error message if status == "failed"
    analysis: str | None = None    # serialized FinancialAnalysis JSON
```

### Status Lifecycle

```
uploaded → processing → done
                      ↘ failed
```

| Status | Meaning |
|--------|---------|
| `uploaded` | File saved to disk, DB row created, analysis not yet started |
| `processing` | Background analysis task is running |
| `done` | All pipeline stages completed, `analysis` JSON populated |
| `failed` | Pipeline encountered an unrecoverable error, `error` message stored |

---

## Analysis JSON Blob

The `analysis` field stores the full `FinancialAnalysis` object serialized to a JSON string.

### Structure of `FinancialAnalysis`

```json
{
  "identity": {
    "company": "Apple Inc.",
    "period": "Q3 FY2024",
    "doc_type": "10-Q"
  },
  "structure": {
    "outline": [...]
  },
  "metrics": [
    {
      "name": "revenue",
      "label": "Revenue",
      "period": "Q3 FY2024",
      "value": "$85.8B",
      "value_numeric": 85800,
      "unit": "USD_millions",
      "basis": "GAAP",
      "source": "Net sales were $85.8 billion..."
    },
    ...
  ],
  "tone": {
    "sentiment": "positive",
    "confidence": "high",
    "hedging": "low",
    "key_passages": [...]
  },
  "risk_factors": [...],
  "memo": {
    "overview": "...",
    "bull_case": [...],
    "bear_case": [...],
    "key_risks": [...],
    "questions_for_management": [...]
  }
}
```

---

## File Storage

Uploaded files are stored on the local filesystem, not in the database.

- **Default directory:** `uploads/` (configurable via `UPLOAD_DIR` env var)
- **Naming:** original filename preserved (or sanitized to avoid conflicts)
- `Contract.file_path` stores the full path to the file on disk
- When a contract is deleted (`DELETE /contracts/{id}`), both the DB row and the file are removed

In Docker, the `uploads/` directory and `contracts.db` are mounted on a **named volume** (`ledger-data`) to persist data across container restarts.

---

## Startup Recovery

On application startup, `main.py` runs a recovery query:

```python
stale = session.exec(
    select(Contract).where(Contract.status.in_(["uploaded", "processing"]))
).all()
for contract in stale:
    contract.status = "failed"
    contract.error = "Server restarted during analysis"
session.commit()
```

This prevents zombie rows — documents that were mid-analysis when the server was killed will be marked `failed` rather than stuck in `processing` forever.

---

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| `DB_PATH` | `contracts.db` | Path to the SQLite database file |
| `UPLOAD_DIR` | `uploads` | Directory for storing uploaded files |

In Docker Compose, these are set to `/data/contracts.db` and `/data/uploads` respectively, both inside the `ledger-data` volume.

---

## Key Dependencies

- `sqlmodel` — ORM combining SQLAlchemy + Pydantic for table definitions and queries
- `sqlite3` — built into Python standard library; no external DB server needed
- `pydantic` — used to serialize/deserialize the `FinancialAnalysis` JSON blob
