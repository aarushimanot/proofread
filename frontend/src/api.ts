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
  collection_id: string | null;
  passages_searched: number;
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
  collection_id: string;
  title: string;
  source: string;
  url: string;
  date: string;
  text: string;
  origin: "seed" | "user";
}

export interface Collection {
  id: string;
  name: string;
  description: string;
  origin: "seed" | "user";
  created_at: string;
  passage_count: number;
}

// A passage before it is saved (from an import preview or the manual form).
export interface PassageDraft {
  title: string;
  source: string;
  url: string;
  date: string;
  text: string;
}

export interface ImportPreview {
  title: string;
  source: string;
  url: string;
  date: string;
  truncated: boolean;
  passages: PassageDraft[];
}

export interface Example {
  id: string;
  collection_id: string;
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
  collection_id: string | null;
  collection_name: string | null;
  claim: string;
  verdict: Verdict;
  confidence: number | null;
  confidence_label: "Low" | "Medium" | "High";
  top_passage_id: string | null;
  timestamp: string;
}

export interface Stats {
  collections: number;
  passages: number;
  test_claims: number;
  reviews: number;
  reviews_agreed: number;
  checks: number;
}

async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: method ?? (body === undefined ? "GET" : "POST"),
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

const q = (collectionId?: string | null) => (collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : "");

export const api = {
  extract: (post_text: string) => request<ExtractResponse>("/extract", { post_text }),
  // collection_id null = check against all topics
  verify: (claim: string, collection_id: string | null) =>
    request<VerifyResponse>("/verify", { claim, collection_id }),
  references: (collectionId?: string | null) => request<Reference[]>(`/references${q(collectionId)}`),
  examples: (collectionId?: string | null) => request<Example[]>(`/examples${q(collectionId)}`),

  collections: () => request<Collection[]>("/collections"),
  createCollection: (name: string, description: string) =>
    request<Collection>("/collections", { name, description }),
  deleteCollection: (id: string) => request<{ deleted: string }>(`/collections/${encodeURIComponent(id)}`, undefined, "DELETE"),
  addPassages: (collection_id: string, passages: PassageDraft[]) =>
    request<Reference[]>("/references", { collection_id, passages }),
  updatePassage: (id: string, fields: Partial<PassageDraft>) =>
    request<Reference>(`/references/${encodeURIComponent(id)}`, fields, "PUT"),
  deletePassage: (id: string) => request<{ deleted: string }>(`/references/${encodeURIComponent(id)}`, undefined, "DELETE"),
  importUrl: (url: string) => request<ImportPreview>("/import/url", { url }),
  importText: (body: { text: string; title: string; source: string; url: string; date: string }) =>
    request<ImportPreview>("/import/text", body),

  review: (entry: { claim: string; model_verdict: Verdict; reviewer_verdict: Verdict; note: string; collection_id: string | null }) =>
    request<{ saved: boolean; entry: ReviewEntry; total: number }>("/review", entry),
  reviewLog: () => request<ReviewEntry[]>("/review-log"),
  history: () => request<CheckRecord[]>("/history"),
  stats: () => request<Stats>("/stats"),
};
