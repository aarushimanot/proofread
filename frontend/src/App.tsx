// App shell: header, persistent disclaimer banner and tabs.
// The list of topics lives here so every tab sees the same, up-to-date list.
import { useCallback, useEffect, useState } from "react";
import { api, type Collection } from "./api";
import About from "./components/About";
import CheckClaim from "./components/CheckClaim";
import History from "./components/History";
import Library from "./components/Library";

const TABS = [
  { id: "check", label: "Check a claim" },
  { id: "library", label: "Lie-brary" },
  { id: "history", label: "History" },
  { id: "about", label: "About & Limitations" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<TabId>("check");
  const [collections, setCollections] = useState<Collection[]>([]);

  const reloadCollections = useCallback(async () => {
    try {
      setCollections(await api.collections());
    } catch {
      setCollections([]);
    }
  }, []);
  useEffect(() => { reloadCollections(); }, [reloadCollections]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" className="h-10 w-10" />
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Proofread</h1>
              <p className="text-sm text-slate-500">Read it for proof before you share it.</p>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto" aria-label="Sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                aria-current={tab === t.id ? "page" : undefined}
                className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
                  tab === t.id ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Persistent human-in-the-loop banner */}
      <div className="border-b border-amber-200 bg-amber-50">
        <p className="mx-auto max-w-5xl px-4 py-2.5 text-sm text-amber-900">
          <strong>Decision-support tool for human reviewers.</strong> Verdicts are based only on the curated reference
          set and may be wrong. Absence of evidence ≠ false.
        </p>
      </div>

      <main className="mx-auto max-w-5xl px-4 py-6">
        {/* Keep CheckClaim mounted so switching tabs doesn't lose the current check. */}
        <div hidden={tab !== "check"}>
          <CheckClaim collections={collections} onManageSources={() => setTab("library")} />
        </div>
        {tab === "library" && <Library collections={collections} onChange={reloadCollections} />}
        {tab === "history" && <History />}
        {tab === "about" && <About />}
      </main>

      <footer className="mx-auto max-w-5xl px-4 pb-8 text-xs text-slate-400">
        Proofread · student media club hackathon prototype · open-source models, no paid APIs
      </footer>
    </div>
  );
}
