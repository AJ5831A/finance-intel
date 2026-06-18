import { useEffect, useRef, useState } from "react";
import { getFollowUps, sendFollowUp } from "../api/client";
import type { FollowUpMessage } from "../types";

/**
 * Human-in-the-loop follow-up panel. Shows the shared conversation for a filing
 * (one thread per contract, server-persisted) and a sticky bottom bar to ask a
 * follow-up. The backend answers grounded in the analysis it already generated.
 */
export function FollowUpBar({ contractId }: { contractId: number }) {
  const [messages, setMessages] = useState<FollowUpMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getFollowUps(contractId).then((r) => setMessages(r.messages)).catch(() => {});
  }, [contractId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function send() {
    const question = draft.trim();
    if (!question || pending) return;
    setPending(true);
    setError(null);
    setDraft("");
    try {
      const r = await sendFollowUp(contractId, question);
      setMessages(r.messages);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setDraft(question); // keep what they typed so it isn't lost
    } finally {
      setPending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <section className="mt-10">
      <h2 className="eyebrow mb-3">Follow up</h2>

      <div className="panel">
        {/* Transcript */}
        <div className="max-h-[420px] space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && !pending && (
            <p className="text-sm text-muted">
              Ask a follow-up about this filing — e.g.{" "}
              <span className="italic">what's driving the margin change?</span>
            </p>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  "max-w-[85%] whitespace-pre-wrap px-3 py-2 text-sm leading-relaxed " +
                  (m.role === "user"
                    ? "bg-cobalt text-white"
                    : "border border-line bg-sunken text-ink/90")
                }
              >
                {m.content}
              </div>
            </div>
          ))}
          {pending && (
            <div className="flex justify-start">
              <div className="border border-line bg-sunken px-3 py-2 text-sm text-muted">
                Thinking…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {error && (
          <p className="border-t border-line px-4 py-2 font-mono text-xs text-[#B23322]">
            {error}
          </p>
        )}

        {/* Bottom bar */}
        <div className="sticky bottom-0 flex items-end gap-2 border-t border-line bg-surface p-3">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask a follow-up…  (Enter to send · Shift+Enter for a new line)"
            className="min-h-[40px] max-h-40 flex-1 resize-y border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-cobalt"
          />
          <button
            onClick={send}
            disabled={pending || !draft.trim()}
            className="h-10 shrink-0 bg-cobalt px-5 font-mono text-xs uppercase tracking-label text-white disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </section>
  );
}
