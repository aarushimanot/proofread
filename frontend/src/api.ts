// Typed client for the Proofread FastAPI backend.
// In the normal setup (./start.sh) FastAPI serves this UI itself, so the API is on the
// same origin (""). In dev mode (Vite on :5173) the API is at http://localhost:8000.
// Either can be overridden with VITE_API_URL (e.g. in a .env file).
const API_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

export type Verdict = "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING";
export const VERDICTS: Verdict[] = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE", "CONFLICTING"];

export interface Candidate {
  sentence: string;
  score: number;
  kept: boolean;
  reasons: string[];
}

export interface ExtractResponse {
  claim: string;
  candidates: Candidate[];
}

export interface Probs {
  entailment: number;
  contradiction: number;
  neutral: number;
}

export interface Mismatch {
  claim_value: string;
  passage_value: string;
  about: string;
}

export interface Evidence {
  id: string;
  title: string;
  source: string;
  url: string;
  date: string;
  text: string;
  similarity: number;
  relevant: boolean;
  stance: "supports" | "contradicts" | "insufficient" | "not_assessed";
  probs: Probs | null;
  raw_probs: Probs | null;
  explanation: string;
  matched_terms: string[];
  number_matches: string[];
  mismatches: Mismatch[];
  gated: boolean;
}

export interface VerifyResponse {
  claim: string;
  verdict: Verdict;
  confidence: number | null;
  confidence_label: "Low" | "Medium" | "High";
  summary: string;
  evidence: Evidence[];
  thresholds: { relevance: number; entailment: number; contradiction: number; mismatch_nudge: number };
  disclaimer: string;
}

export interface Reference {
  id: string;
  title: string;
  source: string;
  url: string;
  date: string;
  text: string;
}

export interface Example {
  id: string;
  post_text: string;
  claim: string;
  expected_verdict: Verdict;
  note: string;
}

export interface ReviewEntry {
  claim: string;
  model_verdict: Verdict;
  reviewer_verdict: Verdict;
  note: string;
  agreed: boolean;
  timestamp: string;
}

export interface CheckRecord {
  id: number;
  claim: string;
  verdict: Verdict;
  confidence: number | null;
  confidence_label: "Low" | "Medium" | "High";
  top_passage_id: string | null;
  timestamp: string;
}

export interface Stats {
  passages: number;
  test_claims: number;
  reviews: number;
  reviews_agreed: number;
  checks: number;
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error(`Cannot reach the Proofread server${API_URL ? ` at ${API_URL}` : ""}. Is ./start.sh running?`);
  }
  if (!res.ok) {
    // FastAPI puts validation messages in `detail`.
    const data = await res.json().catch(() => ({}));
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d: { msg: string }) => d.msg).join("; ")
      : data.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  extract: (post_text: string) => request<ExtractResponse>("/extract", { post_text }),
  verify: (claim: string) => request<VerifyResponse>("/verify", { claim }),
  references: () => request<Reference[]>("/references"),
  examples: () => request<Example[]>("/examples"),
  review: (entry: { claim: string; model_verdict: Verdict; reviewer_verdict: Verdict; note: string }) =>
    request<{ saved: boolean; entry: ReviewEntry; total: number }>("/review", entry),
  reviewLog: () => request<ReviewEntry[]>("/review-log"),
  history: () => request<CheckRecord[]>("/history"),
  stats: () => request<Stats>("/stats"),
};
