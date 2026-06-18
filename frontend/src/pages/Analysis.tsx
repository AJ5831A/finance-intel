import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getDocument } from "../api/client";
import type { ContractDetail } from "../types";
import { ToneGauge } from "../components/ToneGauge";
import { MetricsTable } from "../components/MetricsTable";
import { ChunkProgress } from "../components/ChunkProgress";
import { FollowUpBar } from "../components/FollowUpBar";
import { severityColor, titleCase } from "../lib/finance";

function Notice({ title, body }: { title: string; body?: string }) {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="eyebrow">{title}</div>
      {body && <p className="mt-3 font-mono text-sm text-muted">{body}</p>}
    </div>
  );
}

export function Analysis() {
  const { id } = useParams();
  const [c, setC] = useState<ContractDetail | null>(null);

  useEffect(() => {
    const poll = () => getDocument(Number(id)).then(setC);
    poll();
    const t = setInterval(poll, 2000);
    return () => clearInterval(t);
  }, [id]);

  if (!c) return <Notice title="Loading…" />;
  if (c.status === "failed")
    return <Notice title="Analysis failed" body={c.error ?? "Unknown error."} />;
  if (c.status !== "done") return <ChunkProgress progress={c.progress} />;

  const a = c.analysis!;
  const idn = a.identity;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
        <div>
          <div className="eyebrow">
            {idn.doc_type || "Filing"} {idn.period ? `· ${idn.period}` : ""}
          </div>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight">
            {idn.company || c.filename}
          </h1>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Link to={`/contracts/${id}/memo`} className="font-mono text-xs uppercase tracking-label text-cobalt hover:underline">
            Investment memo →
          </Link>
          <Link to={`/contracts/${id}/document`} className="font-mono text-xs uppercase tracking-label text-cobalt hover:underline">
            Document →
          </Link>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="order-2 space-y-8 lg:order-1">
          <section>
            <h2 className="eyebrow mb-3">Financial metrics</h2>
            <MetricsTable metrics={a.metrics} />
          </section>

          <section>
            <h2 className="eyebrow mb-3">Risk factors · {a.risk_factors.length}</h2>
            {a.risk_factors.length === 0 ? (
              <p className="panel p-5 text-sm text-muted">No risk factors extracted.</p>
            ) : (
              <ul className="space-y-2">
                {a.risk_factors.map((r, i) => (
                  <li key={i} className="panel p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-baseline gap-3">
                        <span
                          className="mt-1 h-2 w-2 shrink-0 rotate-45"
                          style={{ background: severityColor(r.severity) }}
                        />
                        <h3 className="font-display font-semibold leading-tight">{r.title}</h3>
                      </div>
                      <span className="font-mono text-[0.68rem] uppercase tracking-label text-muted">
                        {titleCase(r.category)}
                      </span>
                    </div>
                    {r.text && <p className="mt-2 pl-5 text-sm leading-relaxed text-muted">{r.text}</p>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="order-1 space-y-4 lg:order-2">
          <ToneGauge tone={a.tone} />
        </aside>
      </div>

      <FollowUpBar contractId={Number(id)} />
    </div>
  );
}
