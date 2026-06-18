import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  uploadDocument,
  analyzeDocument,
  listDocuments,
  deleteDocument,
} from "../api/client";

export function Library() {
  const [rows, setRows] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const refresh = () => listDocuments().then(setRows);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const { id } = await uploadDocument(file);
      await analyzeDocument(id);
      if (inputRef.current) inputRef.current.value = "";
      navigate(`/contracts/${id}`);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(e: React.MouseEvent, id: number) {
    e.preventDefault();
    await deleteDocument(id);
    refresh();
  }

  return (
    <div className="mx-auto max-w-6xl px-6">
      <section className="border-b border-line py-14">
        <div className="eyebrow">Fundamental analysis, in seconds</div>
        <h1 className="mt-3 max-w-3xl font-display text-5xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
          Read a filing the way an analyst would, without the hours.
        </h1>
        <p className="mt-5 max-w-xl text-base leading-relaxed text-muted">
          Drop in a 10-K, 10-Q, earnings release, or call transcript. Ledger extracts the
          metrics, reads management's tone, tracks risk factors, and drafts the investment
          memo, leaving the judgment to you.
        </p>

        <div className="mt-8">
          <input
            ref={inputRef}
            id="upload"
            type="file"
            accept=".pdf,.docx"
            onChange={onUpload}
            disabled={busy}
            className="sr-only"
          />
          <label
            htmlFor="upload"
            className={`inline-flex cursor-pointer items-center gap-3 bg-ink px-5 py-3 font-mono text-xs uppercase tracking-label text-surface transition-opacity focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-cobalt ${
              busy ? "opacity-50" : "hover:opacity-90"
            }`}
          >
            <span aria-hidden>＋</span>
            {busy ? "Ingesting filing…" : "Analyse a filing"}
          </label>
          <span className="ml-4 font-mono text-[0.68rem] uppercase tracking-label text-muted">
            PDF or DOCX
          </span>
        </div>
      </section>

      <section className="py-10">
        <div className="flex items-baseline justify-between">
          <h2 className="eyebrow">Filings · {rows.length}</h2>
          <Link
            to="/benchmark"
            className="font-mono text-xs uppercase tracking-label text-cobalt hover:underline"
          >
            Benchmark →
          </Link>
        </div>

        {rows.length === 0 ? (
          <p className="mt-6 border border-dashed border-line bg-surface/60 p-8 text-center text-sm text-muted">
            No filings yet. Upload one above to run the first analysis.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-line border border-line bg-surface">
            {rows.map((r) => (
              <li key={r.id} className="flex items-center gap-4 px-4 py-3">
                <Link
                  to={`/contracts/${r.id}`}
                  className="font-display font-semibold text-ink hover:text-cobalt"
                >
                  {r.company || r.filename}
                </Link>
                {r.period && (
                  <span className="font-mono text-[0.68rem] uppercase tracking-label text-muted">
                    {r.period}
                  </span>
                )}
                {r.doc_type && (
                  <span className="border border-line px-1.5 py-0.5 font-mono text-[0.6rem] uppercase tracking-label text-muted">
                    {r.doc_type}
                  </span>
                )}
                <span className="ml-auto font-mono text-[0.68rem] uppercase tracking-label text-muted">
                  {r.status}
                </span>
                <button
                  onClick={(e) => onDelete(e, r.id)}
                  className="font-mono text-[0.68rem] uppercase tracking-label text-muted hover:text-risk-high"
                  aria-label={`Delete ${r.filename}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
