// Small shared UI pieces: spinner, error box, verdict badge, section card.
import type { ReactNode } from "react";
import type { Verdict } from "../api";

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      {label}
    </span>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      <strong className="font-semibold">Something went wrong: </strong>
      {message}
    </div>
  );
}

// Colour scheme per verdict: green supported, red contradicted, grey insufficient, amber conflicting.
export const VERDICT_STYLES: Record<Verdict, { label: string; badge: string; panel: string }> = {
  SUPPORTED: {
    label: "Supported",
    badge: "bg-green-600 text-white",
    panel: "border-green-200 bg-green-50",
  },
  CONTRADICTED: {
    label: "Contradicted",
    badge: "bg-red-600 text-white",
    panel: "border-red-200 bg-red-50",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient evidence",
    badge: "bg-slate-500 text-white",
    panel: "border-slate-200 bg-slate-100",
  },
  CONFLICTING: {
    label: "Conflicting evidence",
    badge: "bg-amber-500 text-white",
    panel: "border-amber-200 bg-amber-50",
  },
};

export function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "px-2 py-0.5 text-xs", md: "px-3 py-1 text-sm", lg: "px-4 py-1.5 text-base" };
  return (
    <span className={`inline-block rounded-full font-semibold uppercase tracking-wide ${sizes[size]} ${VERDICT_STYLES[verdict].badge}`}>
      {VERDICT_STYLES[verdict].label}
    </span>
  );
}

export function Card({ step, title, children }: { step?: number; title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="mb-4 flex items-center gap-3 text-lg font-semibold text-slate-900">
        {step !== undefined && (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm text-white">
            {step}
          </span>
        )}
        {title}
      </h2>
      {children}
    </section>
  );
}

export const buttonPrimary =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50";
export const buttonSecondary =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
export const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
