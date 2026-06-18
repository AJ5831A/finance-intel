BLOCK_MAP_PROMPT = """You are a financial-document parser. You are given ONE EXCERPT from a
larger filing (10-K/10-Q, earnings release, or transcript). Break the excerpt into ordered
structural blocks. For each block emit:
- type: "header" (a top-level section like "Risk Factors" or "Management's Discussion"),
  "subheader" (a sub-section), or "paragraph" (running text, table rows, or a bullet).
- number: the section number if present (e.g. "1A", "7"), else null.
- text: the verbatim text of the block. For headers/subheaders this is the heading line;
  for paragraphs it is the prose, table line, or bullet.
Preserve reading order. Do not summarize or invent content. Excerpt:

{text}
"""

OUTLINE_SYNTH_PROMPT = """You are assembling the table of contents for a financial filing. Below
are the headings and sub-headings extracted in order (some may be duplicated or fragmented
because they came from overlapping excerpts). Produce a clean, de-duplicated outline and a
concise document title. For each outline entry give number (or null), title, and level (1 for
sections, 2 for sub-sections). Keep document order.

Headings:
{headings}
"""

IDENTITY_PROMPT = """From the opening of this financial document, identify:
- company: the reporting company's name (or null).
- period: the fiscal period it covers, e.g. "Q4 2024" or "FY2024" (or null).
- doc_type: one of "earnings release", "10-K", "10-Q", "transcript", or "other".

Document opening:
{text}
"""

METRICS_PROMPT = """You are a financial analyst. From this excerpt of a filing, extract every
named financial figure. Map each to one of these canonical names where it fits, otherwise use a
clear snake_case name: {canonical}.

For each metric return:
- name: canonical snake_case name.
- label: the figure's label as written (e.g. "Non-GAAP gross margin").
- period: the period it applies to (e.g. "Q4 2024", "FY2024"), or null.
- value: the figure exactly as reported (e.g. "$14.3 billion", "39.2%").
- value_numeric: the value as a plain number normalized to `unit` (e.g. 14300 for "$14.3B" in
  USD millions; 39.2 for "39.2%"), or null if not parseable.
- unit: "USD millions", "%", "USD", etc.
- basis: "GAAP", "non-GAAP", or null.
- source: a short verbatim snippet showing where the figure came from.

Do not invent figures. Only extract what is explicitly stated. Excerpt:

{text}
"""

TONE_PROMPT = """You are analysing management's tone in the commentary below. Assess:
- overall_sentiment: confident | cautious | neutral | mixed.
- confidence_score: 0-100 (how assertive/optimistic management sounds).
- hedging_level: low | medium | high (use of hedging/uncertain language).
- summary: one or two sentences describing the tone.
- passages: pick the few most telling passages. For each, give the verbatim text, its sentiment
  (confident/cautious/neutral/mixed), a confidence 0-100, hedging (low/medium/high), and a short
  rationale. Be sure to surface the single most confident and the single most cautious passage.

Commentary:
{text}
"""

RISK_FACTORS_PROMPT = """You are a financial analyst. From this excerpt, extract the distinct risk
factors the company discloses. For each: category (e.g. market, operational, regulatory,
financial, technology, geopolitical, legal), a short title, the disclosed text (condensed if
long), and a severity 0-100 reflecting how material it reads. Only extract disclosed risks.
Excerpt:

{text}
"""

RISK_COMPARE_PROMPT = """You are comparing a company's disclosed risk factors across two periods.
For each risk in the CURRENT period, classify it versus the PRIOR period as:
- "new" (not present prior), "escalated" (present but materially expanded/worsened),
  "unchanged" (substantively the same). Also list any PRIOR risks dropped in current as "removed".
Match risks by meaning, not exact wording. Give title, category, status, and a short rationale.

PRIOR period risks:
{prior}

CURRENT period risks:
{current}
"""

MEMO_PROMPT = """You are an equity analyst writing an investment memo. Use ONLY the extracted data
provided below — do not introduce figures or facts not present here. Write:
- company_overview: 2-3 sentences.
- financial_summary: the headline financial picture, citing the provided metrics.
- bull_case: 3-5 specific points supporting the stock, grounded in the data.
- bear_case: 3-5 specific points against, grounded in the data.
- key_risks: the most material risks.
- questions: 3-5 sharp questions an analyst should investigate next.

Extracted data:
{findings}
"""

BENCHMARK_PROMPT = """You are comparing companies on the metric grid below (rows are companies,
columns are metrics). Write a list of the substantive highlights a portfolio analyst would care
about: who leads on each metric, notable gaps in growth/margins/leverage, and any outliers.

Grid:
{grid}
"""

FOLLOWUP_PROMPT = """You are an equity analyst assistant answering a follow-up question about a
filing you have already analysed. Use ONLY the analysis context below — do not introduce figures
or facts not present in it. If the context does not contain the answer, say so plainly and point
to where it would be found (which document section or filing). Be concise and specific; cite the
metric, risk, or passage you are drawing on.

ANALYSIS CONTEXT:
{context}

CONVERSATION SO FAR:
{history}

QUESTION:
{question}
"""
