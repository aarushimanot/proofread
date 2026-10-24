// One retrieved reference passage, with highlighting, scores and the explanation.
import type { Evidence, Probs } from "../api";

const STANCE_TAGS: Record<Evidence["stance"], { label: string; cls: string }> = {
  supports: { label: "Supports", cls: "bg-green-100 text-green-800 ring-green-200" },
  contradicts: { label: "Contradicts", cls: "bg-red-100 text-red-800 ring-red-200" },
  insufficient: { label: "Neither confirms nor refutes", cls: "bg-slate-100 text-slate-700 ring-slate-200" },
  not_assessed: { label: "Not relevant", cls: "bg-slate-100 text-slate-500 ring-slate-200" },
};

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Wrap every matched term in <mark> (case-insensitive, whole words).
function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  if (terms.length === 0) return <>{text}</>;
  const sorted = [...terms].sort((a, b) => b.length - a.length); // longest first
  const pattern = new RegExp(`\\b(${sorted.map(escapeRegExp).join("|")})\\b`, "gi");
  const lower = new Set(terms.map((t) => t.toLowerCase()));
  return (
    <>
      {text.split(pattern).map((part, i) =>
        lower.has(part.toLowerCase()) ? (
          <mark key={i} className="rounded bg-yellow-200 px-0.5 text-slate-900">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

function SimilarityBar({ value, threshold }: { value: number; threshold: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>Similarity</span>
        <span className="font-mono">{value.toFixed(2)}</span>
      </div>
      <div className="relative h-2 rounded-full bg-slate-200">
        <div
          className={`h-2 rounded-full ${value >= threshold ? "bg-indigo-500" : "bg-slate-400"}`}
          style={{ width: `${pct}%` }}
        />
        {/* Marker showing the relevance threshold */}
        <div
          className="absolute -top-1 h-4 w-0.5 bg-slate-700"
          style={{ left: `${threshold * 100}%` }}
          title={`Relevance threshold ${threshold}`}
        />
      </div>
    </div>
  );
}

function ProbRow({ probs }: { probs: Probs }) {
  const items: [keyof Probs, string, string][] = [
    ["entailment", "Entails", "bg-green-500"],
    ["contradiction", "Contradicts", "bg-red-500"],
    ["neutral", "Neutral", "bg-slate-400"],
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      {items.map(([key, label, color]) => (
        <div key={key}>
          <div className="mb-1 flex justify-between text-xs text-slate-500">
            <span>{label}</span>
            <span className="font-mono">{(probs[key] * 100).toFixed(0)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-slate-200">
            <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${probs[key] * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function EvidenceCard({ item, threshold }: { item: Evidence; threshold: number }) {
  const tag = STANCE_TAGS[item.stance];
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="font-semibold text-slate-900">{item.title}</h4>
          <p className="mt-0.5 text-xs text-slate-500">
            {item.source} · {item.date} ·{" "}
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="break-all text-indigo-600 underline hover:text-indigo-800">
              {item.url}
            </a>
          </p>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${tag.cls}`}>{tag.label}</span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-slate-700">
        <Highlighted text={item.text} terms={item.matched_terms} />
      </p>

      <div className="mt-4 space-y-3">
        <SimilarityBar value={item.similarity} threshold={threshold} />
        {item.probs && <ProbRow probs={item.probs} />}
      </div>

      {item.mismatches.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {item.mismatches.map((m, i) => (
            <p key={i}>
              ⚠ <strong>Number/date mismatch</strong> about “{m.about}”: claim says <strong>{m.claim_value}</strong>,
              passage says <strong>{m.passage_value}</strong>.
            </p>
          ))}
        </div>
      )}

      <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600">
        <span className="font-medium text-slate-700">Why: </span>
        {item.explanation}
      </p>
    </article>
  );
}
