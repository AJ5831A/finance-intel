"""Human-in-the-loop follow-up answering.

The human reads a filing's generated analysis and asks follow-up questions. We
answer grounded in the ALREADY-EXTRACTED findings (identity, metrics, tone, risks,
memo, outline) — the same principle as memo generation — rather than the raw
document, so answers stay consistent with what the user sees on screen and the
prompt stays bounded. Prior turns are threaded in so the thread is conversational.
"""
from app.llm.prompts import FOLLOWUP_PROMPT


def _build_context(analysis: dict) -> str:
    analysis = analysis or {}
    lines: list[str] = []

    ident = analysis.get("identity") or {}
    lines.append(
        f"Company: {ident.get('company') or 'unknown'} | "
        f"Period: {ident.get('period') or 'n/a'} | "
        f"Type: {ident.get('doc_type') or 'n/a'}")

    lines.append("\nMETRICS:")
    for m in analysis.get("metrics", []):
        period = f" ({m.get('period')})" if m.get("period") else ""
        basis = f" [{m.get('basis')}]" if m.get("basis") else ""
        lines.append(f"- {m.get('name')}{period}: {m.get('value')}{basis}")

    tone = analysis.get("tone") or {}
    if tone:
        lines.append(
            f"\nTONE: {tone.get('overall_sentiment')} "
            f"(confidence {tone.get('confidence_score')}, "
            f"hedging {tone.get('hedging_level')}). {tone.get('summary', '')}")
        for p in tone.get("passages", []):
            lines.append(f'  · "{p.get("text", "")}" — {p.get("sentiment")} '
                         f'({p.get("rationale", "")})')

    lines.append("\nRISK FACTORS:")
    for r in analysis.get("risk_factors", []):
        lines.append(f"- [{r.get('category')}] {r.get('title')} "
                     f"(severity {r.get('severity')}): {r.get('text', '')}")

    memo = analysis.get("memo") or {}
    if memo:
        lines.append("\nINVESTMENT MEMO:")
        lines.append(f"Overview: {memo.get('company_overview', '')}")
        lines.append(f"Financial summary: {memo.get('financial_summary', '')}")
        for label, key in (("Bull case", "bull_case"), ("Bear case", "bear_case"),
                           ("Key risks", "key_risks"), ("Questions", "questions")):
            items = memo.get(key) or []
            if items:
                lines.append(f"{label}: " + "; ".join(items))

    structure = analysis.get("structure") or {}
    outline = structure.get("outline") or []
    if outline:
        lines.append("\nDOCUMENT OUTLINE:")
        for e in outline:
            lines.append(f"- {e.get('number') or ''} {e.get('title', '')}".rstrip())

    return "\n".join(lines)


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(no prior messages)"
    role_label = {"user": "User", "assistant": "Assistant"}
    return "\n".join(f"{role_label.get(m['role'], m['role'])}: {m['content']}"
                     for m in history)


def answer_followup(analysis: dict, history: list[dict], question: str, llm) -> str:
    prompt = FOLLOWUP_PROMPT.format(
        context=_build_context(analysis),
        history=_format_history(history),
        question=question)
    return llm.generate_text(prompt)
