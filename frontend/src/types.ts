// --- Document structure (reused from the structuring pipeline) ---
export type BlockType = "header" | "subheader" | "paragraph";
export interface DocumentBlock {
  type: BlockType; number: string | null; text: string;
}
export interface OutlineEntry {
  number: string | null; title: string; level: number;
}
export interface StructuredDocument {
  title: string | null; outline: OutlineEntry[]; blocks: DocumentBlock[];
}

// --- Financial analysis ---
export interface DocumentIdentity {
  company: string | null; period: string | null; doc_type: string | null;
}
export interface Metric {
  name: string; label: string; period: string | null; value: string;
  value_numeric: number | null; unit: string | null; basis: string | null;
  source: string | null;
}
export type Sentiment = "confident" | "cautious" | "neutral" | "mixed";
export interface TonePassage {
  text: string; sentiment: Sentiment; confidence: number;
  hedging: string; rationale: string;
}
export interface ToneAnalysis {
  overall_sentiment: Sentiment; confidence_score: number; hedging_level: string;
  summary: string; passages: TonePassage[];
}
export interface RiskFactor {
  category: string; title: string; text: string; severity: number;
}
export interface InvestmentMemo {
  company_overview: string; financial_summary: string;
  bull_case: string[]; bear_case: string[]; key_risks: string[]; questions: string[];
}
export interface FinancialAnalysis {
  identity: DocumentIdentity; structure: StructuredDocument; metrics: Metric[];
  tone: ToneAnalysis; risk_factors: RiskFactor[]; memo: InvestmentMemo;
}

export interface Progress {
  stage: string; current: number; total: number; preview: string;
}
export interface ContractDetail {
  id: number; filename: string; status: string;
  error: string | null; analysis: FinancialAnalysis | null; progress: Progress | null;
}

// --- Follow-up conversation (human-in-the-loop) ---
export interface FollowUpMessage {
  id: number; role: "user" | "assistant"; content: string; created_at: string;
}

// --- Comparison results ---
export interface BenchmarkRow { company: string; values: Record<string, string | null>; }
export interface Benchmark { metric_names: string[]; rows: BenchmarkRow[]; highlights: string[]; }
export type RiskStatus = "new" | "escalated" | "unchanged" | "removed";
export interface RiskDelta { title: string; category: string; status: RiskStatus; rationale: string; }
export interface RiskComparison {
  prior: { id: number; name: string }; current: { id: number; name: string };
  deltas: RiskDelta[];
}
