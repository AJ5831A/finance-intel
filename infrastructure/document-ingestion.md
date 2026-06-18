# Document Ingestion & Parsing

## Overview

The ingestion module is responsible for taking a raw uploaded file (PDF or DOCX) and converting it into a clean, usable text string that the analysis pipeline can process. It handles multiple formats, gracefully falls back to OCR for scanned documents, and splits large texts into bounded chunks to avoid LLM token limits.

---

## Module Location

`backend/app/ingestion/`

```
ingestion/
├── router.py          # Format dispatcher + fallback logic
├── pdf.py             # pdfplumber-based PDF text extraction
├── docx.py            # python-docx-based DOCX extraction
├── docling_parser.py  # OCR fallback for scanned/image-heavy PDFs
├── chunking.py        # Splits large text into bounded chunks
├── structure.py       # Chunked map-reduce document structuring
└── base.py            # ParsedDocument data model
```

---

## Data Model

**File:** `base.py`

```python
class ParsedDocument:
    full_text: str       # Complete extracted text
    is_degraded: bool    # True if OCR fallback was used
```

---

## Format Dispatcher

**File:** `router.py`

Acts as the single entry point for all parsing. Selects the right parser based on file extension, then checks output quality:

```
file extension == .pdf  → PdfParser
file extension == .docx → DocxParser

if extracted text < 30 characters:
    → flag as degraded
    → retry with DoclingParser (OCR)
```

This fallback handles scanned PDFs (image-only, no text layer) which are common with older SEC filings.

---

## PDF Parser

**File:** `pdf.py`

Uses **pdfplumber** to extract text from native (text-layer) PDFs.

- Opens the PDF file
- Iterates over all pages
- Extracts text from each page
- Concatenates pages with newline separators into a single string

Works well for digitally-created PDFs (most modern 10-K/10-Q filings). Fails gracefully on scanned documents — the router detects the short output and escalates to Docling.

---

## DOCX Parser

**File:** `docx.py`

Uses **python-docx** to extract text from Word documents.

- Opens the `.docx` file
- Iterates over all paragraphs in the document body
- Joins paragraph text with newline separators

Handles earnings releases and transcripts that are often distributed as Word files.

---

## OCR Fallback — Docling Parser

**File:** `docling_parser.py`

Uses **Docling** (which pulls PyTorch under the hood) to perform layout-aware OCR on scanned or image-heavy PDFs.

- Detects text blocks, tables, and layout structures
- Reconstructs reading order
- Returns cleaned full text

This is only invoked when the primary PDF parser returns insufficient text. Because Docling is large and slow, it is installed as an optional dependency.

---

## Chunking

**File:** `chunking.py`

Large financial documents (e.g., 200-page 10-K filings) exceed the context window of most LLM calls. The chunker splits the full text into manageable pieces.

- Accepts a full text string and a max chunk size (in characters)
- Splits on paragraph/section boundaries where possible
- Returns a list of text chunks, each within the size limit

Used by the structuring stage before sending chunks to the LLM.

---

## Document Structuring (Map-Reduce)

**File:** `structure.py`

Converts raw text into a structured outline (headings, sections, subsections). Uses a **chunked map-reduce** pattern to handle documents of any length:

**Map phase** — for each chunk independently:
- Send chunk to Gemini with a prompt to identify headings, sections, and subsections
- Returns a list of parsed blocks for that chunk

**Reduce phase**:
- Merge all per-chunk block lists
- Deduplicate overlapping sections (same heading appearing at chunk boundaries)
- Synthesize a final outline in a single bounded LLM call over the chapter headings only

**Progress streaming:**
- After each chunk is processed, a progress update is pushed to the in-process progress store
- The frontend polls for these updates to drive the `ChunkProgress` animation

---

## Supported Formats

| Format | Parser | Fallback |
|--------|--------|---------|
| `.pdf` (text layer) | pdfplumber | Docling (OCR) |
| `.pdf` (scanned/image) | pdfplumber (fails) | Docling (OCR) |
| `.docx` | python-docx | None |

---

## Key Dependencies

- `pdfplumber` — native PDF text extraction
- `python-docx` — Word document parsing
- `docling` *(optional)* — OCR + layout recovery for scanned PDFs
- `app.llm.client` — used by `structure.py` for LLM-based structuring
- `app.pipeline.progress` — progress store updated during chunk processing
