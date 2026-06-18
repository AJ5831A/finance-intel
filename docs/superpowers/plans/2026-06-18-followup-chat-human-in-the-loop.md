# Follow-up Chat — Human-in-the-Loop Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Implement task-by-task; run the backend test suite (Gemini mocked) after each backend task.

**Goal:** Let a human read a filing's generated analysis (dashboard + investment memo) and ask follow-up questions about it. The system answers with **full context of everything it already generated** — identity, metrics, tone, risk factors, memo, and document outline — plus the running conversation. A persistent **bottom-bar input with a Send button** appears on both the Analysis and Memo pages, backed by **one shared conversation per filing**, persisted in SQLite. Simple request/response (no streaming in v0).

**Decisions locked in (from clarification):**
- **Placement:** bottom bar on *both* `/contracts/:id` (Analysis) and `/contracts/:id/memo` (Memo), sharing one conversation per filing.
- **Persistence:** persist messages in SQLite.
- **Response mode:** simple POST → wait → render full answer. Matches the existing non-streaming `GeminiClient`.

---

## Architecture fit

The follow-up feature reuses the existing patterns rather than inventing new ones:

```
Analysis / Memo page
  │  reads conversation, renders bubbles
  │  bottom bar: <FollowUpBar> textarea + Send
  ▼
POST /contracts/{id}/followup  { question }
  │  1. load Contract (must be status="done")
  │  2. build grounding context from stored analysis JSON   (pipeline/followup.py:_build_context)
  │  3. load prior messages for this contract               (db: FollowUpMessage rows)
  │  4. GeminiClient.generate_text(prompt)                  (NEW plain-text method)
  │  5. persist user msg + assistant msg
  ▼
{ messages: [...] }   ← full updated transcript
GET /contracts/{id}/followup → { messages: [...] }  (load on page mount)
```

**Why these choices:**
- **Grounding context is built from the stored `FinancialAnalysis` JSON**, not the raw document — same principle as `memo.py` (the memo is synthesized from extracted findings). This keeps answers consistent with what the user sees on screen and keeps the prompt bounded (the raw 10-K could be 100+ pages).
- **A new `generate_text` method** on `GeminiClient` — the follow-up answer is free-form prose, not a typed schema, so it bypasses `to_gemini_schema`. The existing retry/backoff loop is reused.
- **A dedicated `FollowUpMessage` table** rather than stuffing messages into `Contract.analysis` — keeps the analysis blob immutable, makes per-message ordering/timestamps natural, and avoids read-modify-write races on the JSON column.

---

## File Structure (new + changed)

```
backend/app/
├── db/
│   └── models.py                 # CHANGE: add FollowUpMessage table
├── schemas/
│   └── financial.py              # CHANGE: add FollowUpTurn / FollowUpRequest (optional, can live in api)
├── llm/
│   ├── client.py                 # CHANGE: add GeminiClient.generate_text(prompt, temperature)
│   └── prompts.py                # CHANGE: add FOLLOWUP_PROMPT
├── pipeline/
│   └── followup.py               # NEW: _build_context(analysis) + answer_followup(...)
└── api/
    └── followup.py               # NEW: GET + POST /contracts/{id}/followup
    main.py                       # CHANGE: include followup.router

frontend/src/
├── types.ts                      # CHANGE: FollowUpMessage type
├── api/client.ts                 # CHANGE: getFollowUps(id), sendFollowUp(id, question)
├── components/
│   └── FollowUpBar.tsx           # NEW: transcript + bottom-bar textarea + Send
├── pages/
│   ├── Analysis.tsx              # CHANGE: mount <FollowUpBar contractId=.../>
│   └── Memo.tsx                  # CHANGE: mount <FollowUpBar contractId=.../>

backend/tests/
└── test_followup.py             # NEW: context builder, endpoint, persistence, not-done guard
```

---

## Backend

### Task 1 — Persistence model
- [ ] In `db/models.py`, add a `FollowUpMessage` SQLModel table:
  - `id: Optional[int]` PK
  - `contract_id: int = Field(index=True, foreign_key="contract.id")`
  - `role: str` — `"user"` | `"assistant"`
  - `content: str`
  - `created_at: datetime = Field(default_factory=datetime.utcnow, index=True)` — for stable ordering.
- [ ] `SQLModel.metadata.create_all` already runs in `init_db()`, so the table is created on startup — no migration needed (SQLite, dev).
- [ ] When a contract is deleted (`api/contracts.py:delete_contract`), also delete its `FollowUpMessage` rows (SQLite has no cascade by default). Add a `session.exec(delete(FollowUpMessage).where(...))` there.

### Task 2 — Plain-text LLM method
- [ ] In `llm/client.py`, add `generate_text(self, prompt: str, temperature: float = 0.3) -> str`:
  - Build `types.GenerateContentConfig(temperature=temperature)` (no `response_mime_type`/`response_schema`).
  - Reuse the same `for attempt in range(self.max_retries)` retry/backoff loop as `generate_structured`.
  - Return `resp.text` (raise `RuntimeError` after retries, mirroring the existing method).
- [ ] Slightly higher default temperature (0.3) than extraction (0.1) — conversational answers, not deterministic extraction.

### Task 3 — Context builder + answer function
- [ ] Create `pipeline/followup.py`.
- [ ] `_build_context(analysis: dict) -> str`: serialize the stored analysis into a compact, labelled block. Reuse the shape of `memo.py:_format_findings` and extend it:
  - Identity line (company · period · doc_type).
  - Metrics: `- {name} ({period}): {value} [{basis}]`.
  - Tone: overall sentiment, confidence, hedging, summary, and the telling passages.
  - Risk factors: `- [{category}] {title} (severity {severity}): {text}`.
  - Memo: overview, financial summary, bull/bear bullets, key risks, questions.
  - Outline: section titles from `structure.outline` (titles only — keeps it bounded).
- [ ] `answer_followup(analysis: dict, history: list[dict], question: str, llm) -> str`:
  - Format `history` as `User: …\nAssistant: …` turns.
  - Fill `FOLLOWUP_PROMPT` with `{context}`, `{history}`, `{question}`.
  - Return `llm.generate_text(prompt)`.
- [ ] Guardrail in the prompt: answer **only** from the provided context; if the data doesn't contain the answer, say so and suggest what document section or filing would (don't hallucinate figures). This mirrors the memo prompt's "use ONLY the extracted data" rule — important for a financial tool.

### Task 4 — Prompt
- [ ] In `llm/prompts.py`, add `FOLLOWUP_PROMPT`:
  ```
  You are an equity analyst assistant answering a follow-up question about a filing
  you have already analysed. Use ONLY the analysis context below — do not introduce
  figures or facts not present in it. If the context doesn't contain the answer, say
  so plainly and point to where it would be found. Be concise and specific; cite the
  metric/risk/passage you're drawing on.

  ANALYSIS CONTEXT:
  {context}

  CONVERSATION SO FAR:
  {history}

  QUESTION:
  {question}
  ```

### Task 5 — API endpoints
- [ ] Create `api/followup.py` with `router = APIRouter(prefix="/contracts", tags=["followup"])`.
- [ ] `GET /{contract_id}/followup` → load messages ordered by `created_at`, return `{"messages": [{id, role, content, created_at}]}`. 404 if contract missing.
- [ ] `POST /{contract_id}/followup` with body `{ "question": str }`:
  - 404 if contract missing; **400 if `status != "done"`** (no analysis to ground on).
  - Reject empty/whitespace question (400).
  - Load history (prior messages) → call `answer_followup(c.analysis, history, question, get_llm())`.
  - Persist the user message then the assistant message (one transaction).
  - Return the **full updated** `{"messages": [...]}` so the frontend re-renders from one source of truth.
- [ ] Reuse `get_llm` (import from `api/contracts.py`, same as `api/compare.py` does).
- [ ] Wire `app.include_router(followup.router)` in `main.py`.

### Task 6 — Backend tests (`tests/test_followup.py`, Gemini mocked)
- [ ] `_build_context` includes metrics, tone, risks, and memo from a sample analysis dict.
- [ ] `POST /followup` on a `done` contract returns user+assistant messages and persists 2 rows (mock `generate_text` to return a fixed string).
- [ ] Second POST includes the first turn in the prompt passed to the mock (history threading).
- [ ] `GET /followup` returns messages in `created_at` order.
- [ ] `POST /followup` on a non-`done` contract → 400; empty question → 400; unknown id → 404.
- [ ] Deleting a contract removes its follow-up messages.

---

## Frontend

### Task 7 — Types + API client
- [ ] `types.ts`: add `FollowUpMessage { id: number; role: "user" | "assistant"; content: string; created_at: string }`.
- [ ] `api/client.ts`: add
  - `getFollowUps(id: number): Promise<{ messages: FollowUpMessage[] }>`
  - `sendFollowUp(id: number, question: string): Promise<{ messages: FollowUpMessage[] }>` (POST JSON).

### Task 8 — `<FollowUpBar>` component
- [ ] New `components/FollowUpBar.tsx`, prop `{ contractId: number }`.
- [ ] On mount, `getFollowUps(contractId)` → render the transcript as bubbles (user right-aligned, assistant left). Empty state: a one-line hint ("Ask a follow-up about this filing — e.g. *what's driving the margin change?*").
- [ ] **Bottom bar:** a sticky/fixed container at the bottom of the content column — a `<textarea>` (auto-grow, Enter to send, Shift+Enter for newline) + a **Send** button. Match the existing Tailwind design tokens (`panel`, `eyebrow`, `text-cobalt`, mono labels) seen in `Analysis.tsx`/`lib/finance.ts`.
- [ ] On Send: optimistically append the user bubble + a "thinking…" placeholder, disable the button, call `sendFollowUp`, then replace local state with the returned `messages`. On error, show an inline error and keep the typed text.
- [ ] Auto-scroll the transcript to the latest message after send.

### Task 9 — Mount on both pages
- [ ] `Analysis.tsx`: render `<FollowUpBar contractId={Number(id)} />` once `status === "done"` (below the metrics/risks grid).
- [ ] `Memo.tsx`: render the same component. Because the conversation is keyed by `contractId` server-side, navigating between Analysis and Memo shows the **same shared thread** — satisfying "system has all the context of what it generated" across both views.

---

## Edge cases & non-goals

- **Only on `done` filings.** While `processing`/`failed`, the bar is hidden (Analysis page already gates on status).
- **Bounded context.** Context is built from the analysis JSON, not raw text; long memos/risk lists are included whole in v0 (the analysis is already a summary, so it stays well within the input budget). If a filing ever produces an oversized context, truncate risk/passage lists — note as a follow-up.
- **No streaming, no auth, no rate limiting** in v0 (matches the rest of the app — single-user dev tool).
- **In-process only assumption holds** — unlike the progress store this is DB-backed, so it survives restarts and would work behind multiple workers.

## Verification
- [ ] `cd backend && ../legalvenv/bin/pytest` — all green (new `test_followup.py` included).
- [ ] Manual: upload + analyze a filing → on the dashboard, ask "which metric moved most and why?" → get a grounded answer → switch to the Memo page → the same thread is visible → ask a second question that references the first → answer reflects the prior turn.
