// Step 3: a human reviewer agrees with or overrides the model verdict.
import { useEffect, useState } from "react";
import { api, VERDICTS, type ReviewEntry, type Verdict } from "../api";
import { VERDICT_STYLES, VerdictBadge, ErrorBox, Spinner, buttonPrimary, inputClass } from "./ui";

interface Props {
  claim: string;
  modelVerdict: Verdict;
  collectionId: string | null;
}

export default function ReviewPanel({ claim, modelVerdict, collectionId }: Props) {
  const [choice, setChoice] = useState<Verdict>(modelVerdict);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [log, setLog] = useState<ReviewEntry[] | null>(null);

  // Reset the form whenever a new verdict comes in.
  useEffect(() => {
    setChoice(modelVerdict);
    setNote("");
    setSaved(false);
  }, [claim, modelVerdict]);

  useEffect(() => {
    api.reviewLog().then(setLog).catch((e: Error) => setError(e.message));
  }, []);

  async function submit() {
    setSaving(true);
    setError("");
    try {
      await api.review({ claim, model_verdict: modelVerdict, reviewer_verdict: choice, note, collection_id: collectionId });
      setSaved(true);
      setLog(await api.reviewLog());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-600">
        The model's verdict is only a suggestion. Read the evidence above, then record your own decision.
      </p>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,16rem)_1fr]">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Reviewer verdict</span>
          <select className={inputClass} value={choice} onChange={(e) => setChoice(e.target.value as Verdict)}>
            <option value={modelVerdict}>Agree: {VERDICT_STYLES[modelVerdict].label}</option>
            {VERDICTS.filter((v) => v !== modelVerdict).map((v) => (
              <option key={v} value={v}>
                Override → {VERDICT_STYLES[v].label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Note (optional)</span>
          <input
            className={inputClass}
            value={note}
            maxLength={2000}
            placeholder="e.g. Passage CY3-05 gives a different date"
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button className={buttonPrimary} onClick={submit} disabled={saving || saved}>
          {saving ? <Spinner /> : null}
          {saved ? "Review saved ✓" : "Submit review"}
        </button>
        {saved && <span className="text-sm text-green-700">Saved to the database</span>}
      </div>
      {error && <ErrorBox message={error} />}

      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Review log</h3>
        {log === null ? (
          <Spinner label="Loading log…" />
        ) : log.length === 0 ? (
          <p className="text-sm text-slate-500">No reviews yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Claim</th>
                  <th className="px-3 py-2">Model</th>
                  <th className="px-3 py-2">Reviewer</th>
                  <th className="px-3 py-2">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {[...log].reverse().map((r, i) => (
                  <tr key={i} className={r.agreed ? "" : "bg-amber-50/60"}>
                    <td className="whitespace-nowrap px-3 py-2 text-slate-500">{new Date(r.timestamp).toLocaleString()}</td>
                    <td className="min-w-[14rem] px-3 py-2 text-slate-800">{r.claim}</td>
                    <td className="px-3 py-2"><VerdictBadge verdict={r.model_verdict} size="sm" /></td>
                    <td className="px-3 py-2"><VerdictBadge verdict={r.reviewer_verdict} size="sm" /></td>
                    <td className="min-w-[10rem] px-3 py-2 text-slate-600">{r.note || "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
