// "Lie-brary": manage topics and the reference passages verdicts are allowed to use.
// Sources can be added by pasting a link, pasting text, or typing a single passage.
// Imports are only a preview until the curator ticks the passages they trust and saves.
import { useEffect, useMemo, useState } from "react";
import { api, type Collection, type ImportPreview, type PassageDraft, type Reference } from "../api";
import { Card, ErrorBox, Spinner, buttonPrimary, buttonSecondary, inputClass } from "./ui";

interface Props {
  collections: Collection[];
  onChange: () => Promise<void> | void;   // ask the app to reload the topic list
}

const today = () => new Date().toISOString().slice(0, 10);
const emptyDraft = (): PassageDraft => ({ title: "", source: "", url: "", date: today(), text: "" });

// ------------------------------------------------------------------ new topic form
function NewTopic({ onCreated }: { onCreated: (c: Collection) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    setBusy(true);
    setError("");
    try {
      const c = await api.createCollection(name, description);
      setName(""); setDescription(""); setOpen(false);
      onCreated(c);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return <button className={`${buttonSecondary} w-full`} onClick={() => setOpen(true)}>+ New topic</button>;
  }
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <input className={inputClass} placeholder="Topic name, e.g. Climate change" value={name} maxLength={80}
             onChange={(e) => setName(e.target.value)} autoFocus />
      <input className={inputClass} placeholder="Short description (optional)" value={description} maxLength={500}
             onChange={(e) => setDescription(e.target.value)} />
      {error && <ErrorBox message={error} />}
      <div className="flex gap-2">
        <button className={buttonPrimary} onClick={create} disabled={name.trim().length < 2 || busy}>
          {busy && <Spinner />} Create
        </button>
        <button className={buttonSecondary} onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ add sources
type Mode = "link" | "text" | "manual";

function AddSources({ collection, onSaved }: { collection: Collection; onSaved: () => void }) {
  const [mode, setMode] = useState<Mode>("link");
  const [url, setUrl] = useState("");
  const [pasted, setPasted] = useState("");
  const [meta, setMeta] = useState<PassageDraft>(emptyDraft());   // title/source/url/date for text + manual
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [picked, setPicked] = useState<boolean[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function reset() {
    setPreview(null); setPicked([]); setError(""); setMessage("");
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const readLink = () => run(async () => {
    const p = await api.importUrl(url);
    setPreview(p);
    setPicked(p.passages.map(() => true));
  });

  const splitText = () => run(async () => {
    const p = await api.importText({ text: pasted, title: meta.title, source: meta.source, url: meta.url, date: meta.date });
    setPreview(p);
    setPicked(p.passages.map(() => true));
  });

  const saveSelected = () => run(async () => {
    const chosen = preview!.passages.filter((_, i) => picked[i]);
    await api.addPassages(collection.id, chosen);
    setMessage(`Saved ${chosen.length} passage(s) to “${collection.name}”.`);
    setPreview(null); setPicked([]); setUrl(""); setPasted("");
    onSaved();
  });

  const saveManual = () => run(async () => {
    await api.addPassages(collection.id, [meta]);
    setMessage(`Saved “${meta.title}” to “${collection.name}”.`);
    setMeta(emptyDraft());
    onSaved();
  });

  const chosenCount = picked.filter(Boolean).length;
  const metaField = (key: keyof PassageDraft, placeholder: string) => (
    <input className={inputClass} placeholder={placeholder} value={meta[key]}
           onChange={(e) => setMeta({ ...meta, [key]: e.target.value })} />
  );
  const tabs: [Mode, string][] = [["link", "Paste a link"], ["text", "Paste text"], ["manual", "Type one passage"]];

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="font-semibold text-slate-900">Add trusted sources to “{collection.name}”</h3>
      <p className="mt-1 text-sm text-amber-800">
        ⚠ Proofread treats everything in a topic as true. Only add sources you trust (official sites, reputable
        news, encyclopedias), and read what you save.
      </p>

      <div className="mt-3 flex flex-wrap gap-1 border-b border-slate-200">
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => { setMode(id); reset(); }}
                  className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                    mode === id ? "border-indigo-600 text-indigo-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {mode === "link" && (
          <>
            <p className="text-sm text-slate-600">
              Paste a web address (e.g. a Wikipedia article or a news story). Proofread reads the page and splits it
              into short passages for you to review.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input className={inputClass} placeholder="https://en.wikipedia.org/wiki/…" value={url}
                     onChange={(e) => setUrl(e.target.value)} />
              <button className={buttonPrimary} onClick={readLink} disabled={busy || url.trim().length < 8}>
                {busy && <Spinner />} Read page
              </button>
            </div>
          </>
        )}

        {mode === "text" && (
          <>
            <p className="text-sm text-slate-600">Copy text from a trusted source and paste it below. It will be split into short passages.</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {metaField("title", "Title, e.g. WHO fact sheet on malaria *")}
              {metaField("source", "Source name, e.g. WHO *")}
              {metaField("url", "Link to the source (recommended)")}
              {metaField("date", "Date (YYYY-MM-DD)")}
            </div>
            <textarea className={`${inputClass} min-h-[140px]`} placeholder="Paste the text here…" value={pasted}
                      onChange={(e) => setPasted(e.target.value)} />
            <button className={buttonPrimary} onClick={splitText}
                    disabled={busy || pasted.trim().length < 20 || meta.title.trim().length < 2 || !meta.source.trim()}>
              {busy && <Spinner />} Split into passages
            </button>
          </>
        )}

        {mode === "manual" && (
          <>
            <p className="text-sm text-slate-600">Write one passage of 2–4 sentences that states facts plainly.</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {metaField("title", "Title *")}
              {metaField("source", "Source name *")}
              {metaField("url", "Link to the source (recommended)")}
              {metaField("date", "Date (YYYY-MM-DD)")}
            </div>
            <textarea className={`${inputClass} min-h-[100px]`} placeholder="Passage text (at least 20 characters) *"
                      value={meta.text} onChange={(e) => setMeta({ ...meta, text: e.target.value })} />
            <button className={buttonPrimary} onClick={saveManual}
                    disabled={busy || meta.text.trim().length < 20 || meta.title.trim().length < 2 || !meta.source.trim()}>
              {busy && <Spinner />} Save passage
            </button>
          </>
        )}

        {error && <ErrorBox message={error} />}
        {message && <p className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-800">✓ {message}</p>}

        {preview && (
          <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium text-slate-900">{preview.title}</p>
                <p className="text-xs text-slate-500">{preview.source} · {preview.date} · {preview.passages.length} passages found
                  {preview.truncated && " (long page: only the first part was used)"}</p>
              </div>
              <div className="flex gap-2 text-sm">
                <button className="text-indigo-700 underline" onClick={() => setPicked(picked.map(() => true))}>Select all</button>
                <button className="text-indigo-700 underline" onClick={() => setPicked(picked.map(() => false))}>Select none</button>
              </div>
            </div>
            <p className="mt-2 text-sm text-slate-600">Untick anything that isn't a clear factual statement (opinions, quotes, menus).</p>
            <div className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto pr-1">
              {preview.passages.map((p, i) => (
                <label key={i} className={`flex cursor-pointer gap-3 rounded-md border bg-white p-3 text-sm ${picked[i] ? "border-indigo-300" : "border-slate-200 opacity-60"}`}>
                  <input type="checkbox" className="mt-1" checked={picked[i] ?? false}
                         onChange={() => setPicked(picked.map((v, j) => (j === i ? !v : v)))} />
                  <span>
                    <span className="block text-xs font-medium text-slate-500">{p.title}</span>
                    <span className="text-slate-700">{p.text}</span>
                  </span>
                </label>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className={buttonPrimary} onClick={saveSelected} disabled={busy || chosenCount === 0}>
                {busy && <Spinner />} Save {chosenCount} selected passage(s)
              </button>
              <button className={buttonSecondary} onClick={reset}>Discard</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ one passage (view / edit)
function PassageCard({ r, onChanged }: { r: Reference; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<PassageDraft>(r);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const builtIn = r.origin === "seed";

  async function save() {
    setBusy(true); setError("");
    try {
      await api.updatePassage(r.id, draft);
      setEditing(false);
      onChanged();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm(`Delete “${r.title}”? This can't be undone.`)) return;
    setBusy(true); setError("");
    try { await api.deletePassage(r.id); onChanged(); }
    catch (e) { setError((e as Error).message); setBusy(false); }
  }

  if (editing) {
    const field = (key: keyof PassageDraft, label: string) => (
      <label className="block text-xs text-slate-500">{label}
        <input className={`${inputClass} mt-0.5`} value={draft[key]} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
      </label>
    );
    return (
      <article className="space-y-2 rounded-lg border border-indigo-300 p-4">
        {field("title", "Title")}
        <div className="grid gap-2 sm:grid-cols-3">{field("source", "Source")}{field("url", "Link")}{field("date", "Date")}</div>
        <label className="block text-xs text-slate-500">Text
          <textarea className={`${inputClass} mt-0.5 min-h-[90px]`} value={draft.text} onChange={(e) => setDraft({ ...draft, text: e.target.value })} />
        </label>
        {error && <ErrorBox message={error} />}
        <div className="flex gap-2">
          <button className={buttonPrimary} onClick={save} disabled={busy}>{busy && <Spinner />} Save</button>
          <button className={buttonSecondary} onClick={() => { setDraft(r); setEditing(false); }}>Cancel</button>
        </div>
      </article>
    );
  }

  return (
    <article className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-slate-900">{r.title}</h3>
        <span className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-xs ${
          r.id.startsWith("DIS") ? "bg-purple-100 text-purple-700" : builtIn ? "bg-slate-100 text-slate-600" : "bg-green-100 text-green-700"}`}>
          {builtIn ? r.id : "added"}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {r.source} · {r.date || "no date"}
        {r.url && <> · <a href={r.url} target="_blank" rel="noopener noreferrer" className="break-all text-indigo-600 underline hover:text-indigo-800">{r.url}</a></>}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-slate-700">{r.text}</p>
      {error && <div className="mt-2"><ErrorBox message={error} /></div>}
      {!builtIn && (
        <div className="mt-2 flex gap-3 text-sm">
          <button className="text-indigo-700 underline" onClick={() => setEditing(true)}>Edit</button>
          <button className="text-red-700 underline" onClick={remove} disabled={busy}>Delete</button>
        </div>
      )}
    </article>
  );
}

// ------------------------------------------------------------------ the tab
export default function Library({ collections, onChange }: Props) {
  const [selected, setSelected] = useState<string>("chandrayaan-3");
  const [refs, setRefs] = useState<Reference[] | null>(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const collection = collections.find((c) => c.id === selected) ?? collections[0];

  async function loadPassages(id: string) {
    setError("");
    try { setRefs(await api.references(id)); } catch (e) { setError((e as Error).message); }
  }

  useEffect(() => {
    if (collection) { setRefs(null); loadPassages(collection.id); }
  }, [collection?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function refresh() {
    if (collection) await loadPassages(collection.id);
    await onChange();                       // update passage counts everywhere
  }

  async function deleteTopic() {
    if (!collection || !window.confirm(`Delete the topic “${collection.name}” and all ${collection.passage_count} of its passages?`)) return;
    try {
      await api.deleteCollection(collection.id);
      setSelected("chandrayaan-3");
      await onChange();
    } catch (e) { setError((e as Error).message); }
  }

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!refs || !q) return refs ?? [];
    return refs.filter((r) => `${r.title} ${r.text} ${r.source} ${r.id}`.toLowerCase().includes(q));
  }, [refs, query]);

  return (
    <Card title="Lie-brary: topics and reference passages">
      <p className="mb-5 text-sm text-slate-600">
        Proofread can only judge a claim against the passages saved here. Create a topic for any subject, add trusted
        sources to it, then pick that topic on the “Check a claim” tab.
      </p>
      <div className="grid gap-6 md:grid-cols-[14rem_1fr]">
        {/* Topic list */}
        <aside className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Topics</h3>
          {collections.map((c) => (
            <button key={c.id} onClick={() => { setSelected(c.id); setQuery(""); }}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm ${
                      collection?.id === c.id ? "bg-indigo-600 text-white" : "bg-slate-50 text-slate-700 hover:bg-slate-100"}`}>
              <span className="truncate">{c.name}</span>
              <span className="ml-2 shrink-0 text-xs opacity-75">{c.passage_count}</span>
            </button>
          ))}
          <NewTopic onCreated={async (c) => { await onChange(); setSelected(c.id); }} />
        </aside>

        {/* Selected topic */}
        <div className="min-w-0 space-y-4">
          {!collection ? <Spinner label="Loading topics…" /> : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">{collection.name}</h3>
                  {collection.description && <p className="text-sm text-slate-600">{collection.description}</p>}
                  <p className="text-xs text-slate-500">
                    {collection.passage_count} passages · {collection.origin === "seed"
                      ? "built-in example (read-only; IDs starting DIS- are deliberate distractors on other missions)"
                      : "your topic"}
                  </p>
                </div>
                {collection.origin === "user" && (
                  <button className="text-sm text-red-700 underline" onClick={deleteTopic}>Delete topic</button>
                )}
              </div>

              {collection.origin === "user" && <AddSources collection={collection} onSaved={refresh} />}

              {error && <ErrorBox message={error} />}
              {refs && refs.length > 0 && (
                <input className={inputClass} placeholder={`Search ${refs.length} passages…`} value={query}
                       onChange={(e) => setQuery(e.target.value)} />
              )}
              {refs === null && !error && <Spinner label="Loading passages…" />}
              {refs && refs.length === 0 && (
                <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-600">
                  No passages yet. Add some trusted sources above.
                </p>
              )}
              <div className="grid gap-3 lg:grid-cols-2">
                {shown.map((r) => <PassageCard key={r.id} r={r} onChanged={refresh} />)}
              </div>
              {refs && refs.length > 0 && shown.length === 0 && (
                <p className="text-sm text-slate-500">No passages match “{query}”.</p>
              )}
            </>
          )}
        </div>
      </div>
    </Card>
  );
}
