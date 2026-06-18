import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getDocument } from "../api/client";
import type { ContractDetail } from "../types";
import { FollowUpBar } from "../components/FollowUpBar";

function Column({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div className="panel p-5">
      <h2 className="eyebrow" style={{ color }}>{title}</h2>
      <ul className="mt-3 space-y-2">
        {items.map((t, i) => (
          <li key={i} className="flex gap-2 text-sm leading-relaxed">
            <span className="select-none" style={{ color }}>—</span>
            <span className="text-ink/90">{t}</span>
          </li>
        ))}
        {items.length === 0 && <li className="text-sm text-muted">—</li>}
      </ul>
    </div>
  );
}

export function Memo() {
  const { id } = useParams();
  const [c, setC] = useState<ContractDetail | null>(null);
  useEffect(() => {
    getDocument(Number(id)).then(setC);
  }, [id]);

  const m = c?.analysis?.memo;
  if (!m)
    return (
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="eyebrow">No memo yet</div>
        <p className="mt-3 font-mono text-sm text-muted">Run the analysis first.</p>
      </div>
    );

  const company = c?.analysis?.identity.company || c?.filename;

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="border-b border-line pb-6">
        <Link to={`/contracts/${id}`} className="font-mono text-xs uppercase tracking-label text-cobalt hover:underline">
          ← Dashboard
        </Link>
        <div className="mt-3 eyebrow">Investment memo</div>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight">{company}</h1>
      </div>

      <div className="mt-8 space-y-8">
        <section>
          <h2 className="eyebrow">Company overview</h2>
          <p className="mt-2 leading-relaxed text-ink/90">{m.company_overview || "—"}</p>
        </section>
        <section>
          <h2 className="eyebrow">Financial summary</h2>
          <p className="mt-2 leading-relaxed text-ink/90">{m.financial_summary || "—"}</p>
        </section>

        <div className="grid gap-4 md:grid-cols-2">
          <Column title="Bull case" items={m.bull_case} color="#1E7A66" />
          <Column title="Bear case" items={m.bear_case} color="#B23322" />
        </div>

        <section>
          <h2 className="eyebrow">Key risks</h2>
          <ul className="mt-3 space-y-2">
            {m.key_risks.map((t, i) => (
              <li key={i} className="border-l-2 border-line pl-3 text-sm leading-relaxed text-ink/90">{t}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="eyebrow">Questions to investigate</h2>
          <ol className="mt-3 space-y-3">
            {m.questions.map((t, i) => (
              <li key={i} className="flex gap-4">
                <span className="font-mono text-sm font-semibold text-cobalt">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-sm leading-relaxed text-ink/90">{t}</span>
              </li>
            ))}
          </ol>
        </section>

        <FollowUpBar contractId={Number(id)} />
      </div>
    </div>
  );
}
