// "History" tab: what is stored in the SQLite database (recent checks + counts).
import { useEffect, useState } from "react";
import { api, type CheckRecord, type Stats } from "../api";
import { Card, ErrorBox, Spinner, VerdictBadge, buttonSecondary } from "./ui";

export default function History() {
  const [checks, setChecks] = useState<CheckRecord[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  function load() {
    setError("");
    Promise.all([api.history(), api.stats()])
      .then(([h, s]) => { setChecks(h); setStats(s); })
      .catch((e: Error) => setError(e.message));
  }
  useEffect(load, []);

  const tiles: [string, number | string][] = stats
    ? [
        ["Topics / passages", `${stats.collections} / ${stats.passages}`],
        ["Claims checked", stats.checks],
        ["Human reviews", stats.reviews],
        ["Reviewer agreed with model", stats.reviews ? `${Math.round((stats.reviews_agreed / stats.reviews) * 100)}%` : "–"],
      ]
    : [];

  return (
    <Card title="History">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-600">Every check and review is stored in Proofread's SQLite database.</p>
        <button className={buttonSecondary} onClick={load}>Refresh</button>
      </div>
      {error && <ErrorBox message={error} />}
      {stats && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-200 p-3">
              <div className="text-2xl font-semibold text-slate-900">{value}</div>
              <div className="text-xs text-slate-500">{label}</div>
            </div>
          ))}
        </div>
      )}
      {checks === null && !error ? (
        <Spinner label="Loading history…" />
      ) : checks && checks.length === 0 ? (
        <p className="text-sm text-slate-500">No claims checked yet.</p>
      ) : checks ? (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Claim</th>
                <th className="px-3 py-2">Topic</th>
                <th className="px-3 py-2">Verdict</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Top passage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {checks.map((c) => (
                <tr key={c.id}>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-500">{new Date(c.timestamp).toLocaleString()}</td>
                  <td className="min-w-[14rem] px-3 py-2 text-slate-800">{c.claim}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-600">{c.collection_name ?? "All topics"}</td>
                  <td className="px-3 py-2"><VerdictBadge verdict={c.verdict} size="sm" /></td>
                  <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                    {c.confidence_label}{c.confidence !== null && ` (${Math.round(c.confidence * 100)}%)`}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-600">{c.top_passage_id ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </Card>
  );
}
