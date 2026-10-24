// "About & Limitations" tab: how it works and what it cannot do.
import { Card } from "./ui";

const LIMITATIONS = [
  ["Small curated corpus", "Only 20 hand-written passages about Chandrayaan-3 (plus 4 distractors). Anything outside them is INSUFFICIENT EVIDENCE."],
  ["NLI weaknesses", "The NLI model is weak on numbers, negation, names that look alike (e.g. it confused “Pragati” with “Pragyan”) and multi-hop reasoning that needs two passages."],
  ["Heuristics", "The number/date mismatch check and the event-alignment gate are hand-written rules. They can misfire, e.g. comparing a Chandrayaan-2 date with a Chandrayaan-3 claim."],
  ["Threshold sensitivity", "Relevance (0.45) and stance (0.6) thresholds were set by hand. Different values change verdicts."],
  ["English only, one claim at a time", "Posts in other languages, or posts making several claims, are not handled."],
  ["Corpus trust", "Verdicts are only as good as the passages. They are paraphrased summaries and must be checked against the linked sources."],
  ["No live updates", "Nothing is fetched from the internet. New facts are invisible until a curator adds them."],
  ["Extraction heuristics", "The claim extractor uses simple rules and may pick the wrong sentence. Always check the claim before verifying."],
  ["Tiny evaluation", "14 test claims, written by the same team that built the system. Accuracy on real posts will be lower."],
];

export default function About() {
  return (
    <div className="space-y-6">
      <Card title="How Proofread works">
        <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
          <li><strong>Extract:</strong> spaCy splits the post into sentences, drops questions, opinions and very short sentences, and scores the rest by named entities, numbers and factual verbs.</li>
          <li><strong>Retrieve:</strong> the claim and every passage are embedded with all-MiniLM-L6-v2. The 3 most similar passages are retrieved; only those with cosine similarity ≥ 0.45 count as relevant.</li>
          <li><strong>Stance:</strong> an NLI model (nli-deberta-v3-small) reads each relevant passage (premise) and the claim (hypothesis) and outputs entailment / contradiction / neutral probabilities.</li>
          <li><strong>Checks:</strong> a number/date check flags passages that give a different value for the same thing; an event-alignment check ignores “contradictions” from passages that describe a different event.</li>
          <li><strong>Rules:</strong> support only → SUPPORTED; contradiction only → CONTRADICTED; both → CONFLICTING; neither, or nothing relevant → INSUFFICIENT EVIDENCE.</li>
        </ol>
        <p className="mt-4 rounded-lg bg-indigo-50 p-3 text-sm text-indigo-900">
          <strong>No match never means false.</strong> A claim is only marked CONTRADICTED when a relevant reference passage
          says something incompatible with it. The models never use their own world knowledge to give a verdict.
        </p>
      </Card>

      <Card title="Limitations">
        <dl className="grid gap-3 sm:grid-cols-2">
          {LIMITATIONS.map(([title, body]) => (
            <div key={title} className="rounded-lg border border-slate-200 p-3">
              <dt className="text-sm font-semibold text-slate-800">{title}</dt>
              <dd className="mt-1 text-sm text-slate-600">{body}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Responsible use">
        <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
          <li>Proofread is a <strong>decision aid for human reviewers</strong>, not an automatic fact checker. A person makes every final call.</li>
          <li>Always open the linked sources. Do not publish a verdict based on the badge alone.</li>
          <li>Record your decision in the review panel, especially when you override the model, so the team can learn where it fails.</li>
          <li>Do not use it to label people or accounts as liars; it assesses one claim against one small reference set.</li>
        </ul>
      </Card>
    </div>
  );
}
