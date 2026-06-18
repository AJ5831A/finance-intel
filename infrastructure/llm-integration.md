# LLM Integration

## Overview

The LLM integration module is Ledger's abstraction layer over the Google Gemini API. It handles all communication with the LLM: constructing requests, validating schemas, parsing structured responses, and managing prompt templates. The design ensures that every LLM call returns a strongly-typed Python object rather than raw text.

---

## Module Location

`backend/app/llm/`

```
llm/
├── client.py    # GeminiClient — wrapper around google-genai SDK
├── schema.py    # Schema sanitizer (Pydantic → Gemini-safe JSON-Schema)
└── prompts.py   # Prompt templates for each analysis stage
```

---

## LLM Client

**File:** `client.py`

`GeminiClient` wraps the `google-genai` Python SDK and provides a single structured-output call method used by every pipeline stage.

### Initialization

```python
client = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
```

Default model: `gemini-2.5-flash` (configurable via `GEMINI_MODEL` env var).

### Core Method

```python
def call(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
```

1. Takes a prompt string and a Pydantic model class as the expected response type
2. Converts the Pydantic model to a Gemini-safe JSON-Schema via `to_gemini_schema()`
3. Sends the request to Gemini with `response_mime_type="application/json"` and the schema
4. Receives the JSON response from Gemini
5. Parses and validates the JSON into the Pydantic model
6. Returns a fully typed Python object

This means all callers in the pipeline receive structured data, never raw strings.

---

## Schema Sanitizer

**File:** `schema.py`

`to_gemini_schema(model: type[BaseModel]) -> dict`

Pydantic's generated JSON-Schema contains constructs that the Gemini API does not support. This sanitizer transforms the schema to be Gemini-compatible.

### Transformations Applied

| Problem | Fix |
|---------|-----|
| `$ref` references | Inline the referenced definition |
| `anyOf` with `null` (Optional fields) | Replace with the non-null type, mark not required |
| `default` keys | Remove (Gemini rejects them) |
| Recursive `$defs` | Flatten and inline |
| Union types (`anyOf` with multiple types) | Simplify to the primary type |

### Why This Is Needed

Pydantic generates standard JSON-Schema Draft 7, but Gemini's structured output mode uses a restricted subset of OpenAPI 3.0 schema. Without this sanitizer, Gemini would reject or misinterpret the schema and return malformed JSON.

---

## Prompt Templates

**File:** `prompts.py`

Contains one prompt function per analysis stage. Each prompt is a formatted string that includes:
- Task instruction for the LLM
- Relevant context (document text or prior stage outputs)
- Output format guidance (reinforces the JSON schema)

### Prompts by Stage

| Stage | Prompt Function | Key Instruction |
|-------|----------------|-----------------|
| Identity | `identity_prompt(text)` | Extract company name, reporting period, document type |
| Metrics | `metrics_prompt(text)` | Extract the 12 canonical financial metrics with values, units, and source excerpts |
| Tone | `tone_prompt(text)` | Analyze management sentiment, confidence level, hedging language, and extract key passages |
| Risk Factors | `risk_factors_prompt(text)` | Identify and categorize all disclosed risks with severity ratings |
| Memo | `memo_prompt(text, identity, metrics, tone, risks)` | Generate a structured investment memo with bull case, bear case, and key questions |
| Benchmark | `benchmark_prompt(metrics_grid)` | Compare metrics across multiple filings, identify outliers and trends |
| Structure (chunk) | `structure_chunk_prompt(chunk)` | Parse a document chunk into headings, sections, and subsections |
| Structure (merge) | `structure_merge_prompt(headings)` | Synthesize a final document outline from the collected headings |

---

## Structured Output Flow

```
Pipeline Stage
  ↓
Call client.call(prompt, ResponseModel)
  ↓
to_gemini_schema(ResponseModel)  →  Gemini-safe schema dict
  ↓
google-genai SDK request
  ↓
Gemini API (gemini-2.5-flash)
  ↓
JSON string response
  ↓
Pydantic model validation
  ↓
Typed Python object returned to pipeline
```

---

## Model Configuration

Configured via environment variables (see `app/config.py`):

| Env Var | Default | Purpose |
|---------|---------|---------|
| `GEMINI_API_KEY` | *(required)* | Google Cloud API key for Gemini access |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model ID to use for all calls |

`gemini-2.5-flash` is chosen for its balance of speed and capability. For higher-quality outputs on complex documents, `gemini-2.5-pro` can be swapped in via the env var.

---

## Error Handling

- Gemini API errors (rate limits, network failures) propagate as exceptions
- The pipeline runner catches these per-stage and marks that stage as failed
- Malformed JSON responses from Gemini cause a Pydantic `ValidationError`, also caught by the runner
- No automatic retries — the runner's graceful degradation handles the failure

---

## Key Dependencies

- `google-genai` — official Google Generative AI Python SDK
- `pydantic` — schema generation and response validation
- `app.schemas.financial` — domain models used as response types
