// "Lie-brary": every reference passage the verdicts are allowed to use.
import { useEffect, useMemo, useState } from "react";
import { api, type Reference } from "../api";
import { Card, ErrorBox, Spinner, inputClass } from "./ui";

export default function Library() {
  const [refs, setRefs] = useState<Reference[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.references().then(setRefs).catch((e: Error) => setError(e.message));
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!refs || !q) return refs ?? [];
    return refs.filter((r) => `${r.title} ${r.text} ${r.source} ${r.id}`.toLowerCase().includes(q));
  }, [refs, query]);

  return (
    <Card title="Lie-brary: the reference passages">
      <p className="mb-4 text-sm text-slate-600">
        Proofread can only judge claims against these passages. Passages with IDs starting <code>DIS-</code> are
        deliberate distractors on other missions, included to test that irrelevant passages are filtered out.
      </p>
      <input
        className={`${inputClass} mb-4`}
        placeholder="Search passages…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {error && <ErrorBox message={error} />}
      {!refs && !error && <Spinner label="Loading references…" />}
      <div className="grid gap-3 md:grid-cols-2">
        {shown.map((r) => (
          <article key={r.id} className="rounded-lg border border-slate-200 p-4">
            <div className="flex items-start justify-between gap-2">
              <h3 className="font-semibold text-slate-900">{r.title}</h3>
              <span className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-xs ${r.id.startsWith("DIS") ? "bg-purple-100 text-purple-700" : "bg-slate-100 text-slate-600"}`}>
                {r.id}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {r.source} · {r.date} ·{" "}
              <a href={r.url} target="_blank" rel="noopener noreferrer" className="break-all text-indigo-600 underline hover:text-indigo-800">
                {r.url}
              </a>
            </p>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{r.text}</p>
          </article>
        ))}
      </div>
      {refs && shown.length === 0 && <p className="text-sm text-slate-500">No passages match “{query}”.</p>}
    </Card>
  );
}
