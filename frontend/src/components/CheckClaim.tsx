// The main three-step workflow: extract a claim, check it, review it.
import { useEffect, useState } from "react";
import { api, type Candidate, type Example, type VerifyResponse } from "../api";
import EvidenceCard from "./EvidenceCard";
import ReviewPanel from "./ReviewPanel";
import {
  Card, ErrorBox, Spinner, VERDICT_STYLES, VerdictBadge,
  buttonPrimary, buttonSecondary, inputClass,
} from "./ui";

export default function CheckClaim() {
  const [examples, setExamples] = useState<Example[]>([]);
  const [post, setPost] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [claim, setClaim] = useState("");
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.examples().then(setExamples).catch(() => setExamples([]));
  }, []);

  function loadExample(id: string) {
    const ex = examples.find((e) => e.id === id);
    if (!ex) return;
    setPost(ex.post_text);
    setCandidates([]);
    setClaim("");
    setResult(null);
    setError("");
  }

  async function extract() {
    setExtracting(true);
    setError("");
    setResult(null);
    try {
      const res = await api.extract(post);
      setCandidates(res.candidates);
      setClaim(res.claim);
      if (!res.claim) setError("No checkable factual sentence was found. Type the claim manually below.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExtracting(false);
    }
  }

  async function verify() {
    setVerifying(true);
    setError("");
    try {
      setResult(await api.verify(claim));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVerifying(false);
    }
  }

  const relevant = result?.evidence.filter((e) => e.relevant) ?? [];
  const notRelevant = result?.evidence.filter((e) => !e.relevant) ?? [];

  return (
    <div className="space-y-6">
      {/* ---------------- Step 1 ---------------- */}
      <Card step={1} title="Paste a post and pick the claim">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <label htmlFor="example" className="text-sm text-slate-600">Load example:</label>
          <select
            id="example"
            className={`${inputClass} w-auto max-w-full sm:max-w-md`}
            defaultValue=""
            onChange={(e) => loadExample(e.target.value)}
          >
            <option value="" disabled>
              {examples.length ? "Choose a test claim…" : "Examples unavailable"}
            </option>
            {examples.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.id} · {ex.claim.length > 60 ? ex.claim.slice(0, 60) + "…" : ex.claim}
              </option>
            ))}
          </select>
        </div>
        <textarea
          className={`${inputClass} min-h-[110px]`}
          placeholder="Paste a social media post here…"
          value={post}
          maxLength={5000}
          onChange={(e) => setPost(e.target.value)}
        />
        <div className="mt-3">
          <button className={buttonPrimary} onClick={extract} disabled={!post.trim() || extracting}>
            {extracting && <Spinner />} Extract claim
          </button>
        </div>

        {candidates.length > 0 && (
          <div className="mt-5">
            <p className="mb-2 text-sm text-slate-600">
              Candidate sentences (best first). Click one to use it as the claim:
            </p>
            <div className="flex flex-wrap gap-2">
              {candidates.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  disabled={!c.kept}
                  title={c.reasons.join(" · ")}
                  onClick={() => { setClaim(c.sentence); setResult(null); }}
                  className={`max-w-full rounded-full border px-3 py-1 text-left text-sm transition ${
                    claim === c.sentence
                      ? "border-indigo-600 bg-indigo-600 text-white"
                      : c.kept
                        ? "border-slate-300 bg-white text-slate-700 hover:border-indigo-400"
                        : "cursor-not-allowed border-dashed border-slate-200 bg-slate-50 text-slate-400 line-through"
                  }`}
                >
                  {c.sentence}
                  <span className="ml-2 font-mono text-xs opacity-70">
                    {c.kept ? c.score : c.reasons[0]?.replace("discarded: ", "")}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <label className="mt-5 block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Claim to check (editable, or type your own)</span>
          <input
            className={inputClass}
            value={claim}
            maxLength={1000}
            placeholder="e.g. Chandrayaan-3 landed near the Moon's south pole."
            onChange={(e) => { setClaim(e.target.value); setResult(null); }}
          />
        </label>
      </Card>

      {/* ---------------- Step 2 ---------------- */}
      <Card step={2} title="Check against references">
        <button className={buttonPrimary} onClick={verify} disabled={claim.trim().length < 3 || verifying}>
          {verifying && <Spinner />} Check against references
        </button>
        {error && <div className="mt-4"><ErrorBox message={error} /></div>}

        {result && (
          <div className="mt-5 space-y-5">
            <div className={`rounded-xl border p-4 ${VERDICT_STYLES[result.verdict].panel}`}>
              <div className="flex flex-wrap items-center gap-3">
                <VerdictBadge verdict={result.verdict} size="lg" />
                <span className="text-sm text-slate-700">
                  {result.verdict === "INSUFFICIENT_EVIDENCE"
                    ? "Confidence that the references don't settle it: "
                    : "Confidence: "}
                  <strong>{result.confidence_label}</strong>
                  {result.confidence !== null && <span className="font-mono"> ({(result.confidence * 100).toFixed(0)}%)</span>}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-500">Claim: “{result.claim}”</p>
              <p className="mt-2 text-slate-800">{result.summary}</p>
              {result.verdict === "CONFLICTING" && (
                <p className="mt-2 text-sm font-medium text-amber-800">Evidence disagrees. A human reviewer must decide.</p>
              )}
            </div>

            <div>
              <h3 className="mb-3 font-semibold text-slate-800">
                Relevant evidence <span className="font-normal text-slate-500">({relevant.length})</span>
              </h3>
              {relevant.length === 0 ? (
                <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600">
                  No reference passage cleared the relevance threshold ({result.thresholds.relevance}). This does
                  <strong> not</strong> mean the claim is false, only that the curated references don't cover it.
                </p>
              ) : (
                <div className="space-y-3">
                  {relevant.map((e) => <EvidenceCard key={e.id} item={e} threshold={result.thresholds.relevance} />)}
                </div>
              )}
            </div>

            {notRelevant.length > 0 && (
              <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <summary className="cursor-pointer text-sm font-medium text-slate-700">
                  Retrieved but not relevant ({notRelevant.length})
                </summary>
                <div className="mt-3 space-y-3">
                  {notRelevant.map((e) => <EvidenceCard key={e.id} item={e} threshold={result.thresholds.relevance} />)}
                </div>
              </details>
            )}

            <p className="text-xs text-slate-500">{result.disclaimer}</p>
          </div>
        )}
      </Card>

      {/* ---------------- Step 3 ---------------- */}
      <Card step={3} title="Human review">
        {result ? (
          <ReviewPanel claim={result.claim} modelVerdict={result.verdict} />
        ) : (
          <p className="text-sm text-slate-500">Check a claim first, then record your decision here.</p>
        )}
      </Card>

      <div className="flex justify-end">
        <button
          className={buttonSecondary}
          onClick={() => { setPost(""); setCandidates([]); setClaim(""); setResult(null); setError(""); }}
        >
          Start over
        </button>
      </div>
    </div>
  );
}
