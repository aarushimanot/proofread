"""
Evaluate Proofread on the labelled test claims.

    python evaluate.py            (or ./start.sh eval from the proofread folder)

What it measures
  1. Full system on the 14 test claims: accuracy, per-class precision/recall/F1,
     confusion matrix, confidence calibration and speed. All 14 were seen while the
     system was being built, so these numbers are optimistic (there is no held-out set).
  2. Baselines: three simpler methods, to show what the full design adds.
  3. Ablations: the full system with one part switched off at a time.
  4. Safety: how often a claim the references do NOT cover is wrongly called false
     (the assignment's key rule), and how often a wrong claim is wrongly supported.
  5. Claim extraction (single claim) and multi-claim posts.
  6. Sensitivity of accuracy to the relevance threshold.

Outputs: results/eval_summary.json (read by the Streamlit app), results/eval_results.csv
and results/eval_report.md. Nothing here changes thresholds: failures are reported as they are.
"""
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone

from app import config, db
from app.aggregator import CONFLICTING, CONTRADICTED, INSUFFICIENT, SUPPORTED, VERDICTS
from app.pipeline import ProofreadPipeline, VerifyOptions
from app.textutils import content_keys

LABELS = [SUPPORTED, CONTRADICTED, INSUFFICIENT]        # the three "true" answers in the test set
FAST = VerifyOptions(explain=False)                     # full system, without UI explanations


# ------------------------------------------------------------------ helpers
def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def same_claim(a: str, b: str) -> bool:
    """Does an extracted sentence correspond to a gold claim? (exact, contained, or 70% word overlap)"""
    a, b = normalise(a), normalise(b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    wa, wb = set(a.split()), set(b.split())
    return len(wa & wb) / len(wa | wb) >= 0.7


def extraction_status(extracted: str, gold: str) -> str:
    e, g = normalise(extracted), normalise(gold)
    if e == g:
        return "exact"
    if g and g in e:
        return "contains"
    return "wrong"


def metrics(expected: list[str], predicted: list[str]) -> dict:
    """Accuracy, macro-F1 over the three true labels, and the safety rates."""
    n = len(expected)
    per_class = {}
    for label in LABELS:
        tp = sum(e == label and p == label for e, p in zip(expected, predicted))
        pred_n = sum(p == label for p in predicted)
        true_n = sum(e == label for e in expected)
        precision = tp / pred_n if pred_n else 0.0
        recall = tp / true_n if true_n else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": true_n, "predicted": pred_n}
    not_covered = [p for e, p in zip(expected, predicted) if e == INSUFFICIENT]
    not_true = [p for e, p in zip(expected, predicted) if e != SUPPORTED]
    correct = sum(e == p for e, p in zip(expected, predicted))
    return {
        "n": n,
        "correct": correct,
        "accuracy": correct / n if n else 0.0,
        "macro_f1": sum(c["f1"] for c in per_class.values()) / len(LABELS),
        "per_class": per_class,
        # The assignment's key rule: "not covered" must never become "false".
        "false_contradiction_rate": (sum(p == CONTRADICTED for p in not_covered) / len(not_covered)) if not_covered else 0.0,
        # A wrong or uncovered claim shown as true is the most harmful error for a fact-checking aid.
        "false_support_rate": (sum(p == SUPPORTED for p in not_true) / len(not_true)) if not_true else 0.0,
        "sent_to_human_rate": sum(p == CONFLICTING for p in predicted) / n if n else 0.0,
    }


def confusion(expected: list[str], predicted: list[str]) -> dict:
    m = {e: {p: 0 for p in VERDICTS} for e in VERDICTS}
    for e, p in zip(expected, predicted):
        m[e][p] += 1
    return m


# ------------------------------------------------------------------ the systems being compared
class Systems:
    """Every method we compare, each a function (claim, topic) -> verdict."""

    def __init__(self, pipeline: ProofreadPipeline):
        self.p = pipeline
        self._keys_cache: dict[str, set] = {}

    # Baseline 1: word overlap. Supported if most of the claim's content words appear in one passage.
    def keyword(self, claim: str, topic: str) -> str:
        claim_keys = set(content_keys(self.p.nlp(claim)))
        best = 0.0
        for passage in db.get_passages(topic):
            if passage["id"] not in self._keys_cache:
                self._keys_cache[passage["id"]] = set(content_keys(self.p.nlp(passage["text"])))
            if claim_keys:
                best = max(best, len(claim_keys & self._keys_cache[passage["id"]]) / len(claim_keys))
        return SUPPORTED if best >= 0.5 else INSUFFICIENT

    # Baseline 2: meaning similarity only. Supported if any passage is very similar in meaning.
    def similarity(self, claim: str, topic: str) -> str:
        hits = self.p.retriever.search(claim, db.get_passages(topic), 1)
        return SUPPORTED if hits and hits[0]["similarity"] >= 0.7 else INSUFFICIENT

    def proofread(self, options: VerifyOptions, top_k: int | None = None):
        return lambda claim, topic: self.p.verify(claim, topic, top_k=top_k, options=options)["verdict"]

    def all(self) -> dict:
        """name -> (group, description, function)."""
        off = dict(explain=False)
        return {
            "Keyword match": ("baseline", "Supported if ≥50% of the claim's content words appear in one passage; otherwise insufficient. Can never say 'contradicted'.", self.keyword),
            "Similarity only": ("baseline", "Supported if the most similar passage has similarity ≥ 0.70; otherwise insufficient. Can never say 'contradicted'.", self.similarity),
            "Plain NLI": ("baseline", "Retrieval + NLI with no relevance threshold and neither heuristic.",
                          self.proofread(VerifyOptions(use_relevance_threshold=False, use_mismatch_check=False, use_event_gate=False, **off))),
            "Proofread (full)": ("full", "The real system: relevance threshold, NLI, number/date check, event-alignment gate.", self.proofread(FAST)),
            "− relevance threshold": ("ablation", "Every retrieved passage counts as relevant.", self.proofread(VerifyOptions(use_relevance_threshold=False, **off))),
            "− number/date check": ("ablation", "No mismatch nudge.", self.proofread(VerifyOptions(use_mismatch_check=False, **off))),
            "− event-alignment gate": ("ablation", "Contradictions about other events are kept.", self.proofread(VerifyOptions(use_event_gate=False, **off))),
            "+ sentence-level NLI": ("ablation", "Each passage judged by its most decisive sentence.", self.proofread(VerifyOptions(sentence_level=True, **off))),
            "top_k = 1": ("ablation", "Only the single most similar passage is used.", self.proofread(FAST, top_k=1)),
            "top_k = 5": ("ablation", "The five most similar passages are used.", self.proofread(FAST, top_k=5)),
        }


# ------------------------------------------------------------------ evaluation steps
def evaluate_full(pipeline: ProofreadPipeline, tests: list[dict]) -> list[dict]:
    """Full system, one row per claim, with extraction and end-to-end results."""
    rows = []
    for t in tests:
        start = time.perf_counter()
        gold = pipeline.verify(t["claim"], t["collection_id"], options=FAST)
        seconds = time.perf_counter() - start
        extracted = pipeline.extract(t["post_text"])["claim"]
        e2e = pipeline.verify(extracted, t["collection_id"], options=FAST)["verdict"] if extracted else INSUFFICIENT
        top = gold["evidence"][0] if gold["evidence"] else None
        rows.append({
            "id": t["id"], "topic": t["collection_id"],
            "claim": t["claim"], "expected": t["expected_verdict"], "predicted": gold["verdict"],
            "correct": gold["verdict"] == t["expected_verdict"],
            "confidence": gold["confidence"], "confidence_label": gold["confidence_label"],
            "top_passage": f"{top['id']} {top['title']}" if top else "",
            "top_similarity": top["similarity"] if top else None,
            "relevant_passages": sum(e["relevant"] for e in gold["evidence"]),
            "stances": "; ".join(f"{e['id']}:{e['stance']}" for e in gold["evidence"]),
            "extracted_claim": extracted, "extraction": extraction_status(extracted, t["claim"]),
            "predicted_e2e": e2e, "seconds": round(seconds, 3), "note": t["note"],
        })
    return rows


def evaluate_multi(pipeline: ProofreadPipeline) -> dict:
    with open(config.MULTI_CLAIM_TESTS_PATH, encoding="utf-8") as f:
        posts = json.load(f)
    details, gold_total, found_total, matched_gold, matched_found, verdict_ok = [], 0, 0, 0, 0, 0
    for post in posts:
        out = pipeline.check_post(post["post_text"], post["collection_id"], options=FAST)
        found = [(r["claim"], r["verdict"]) for r in out["claims"]]
        gold = post["claims"]
        gold_total += len(gold)
        found_total += len(found)
        pairs = []
        for g in gold:
            match = next(((c, v) for c, v in found if same_claim(c, g["claim"])), None)
            if match:
                matched_gold += 1
                verdict_ok += match[1] == g["expected_verdict"]
            pairs.append({"gold": g["claim"], "expected": g["expected_verdict"],
                          "extracted": match[0] if match else None, "predicted": match[1] if match else None})
        matched_found += sum(any(same_claim(c, g["claim"]) for g in gold) for c, _ in found)
        extra = [c for c, _ in found if not any(same_claim(c, g["claim"]) for g in gold)]
        details.append({"id": post["id"], "topic": post["collection_id"], "pairs": pairs, "extra_claims": extra})
    return {
        "posts": len(posts), "gold_claims": gold_total, "extracted_claims": found_total,
        "claim_recall": matched_gold / gold_total if gold_total else 0.0,
        "claim_precision": matched_found / found_total if found_total else 0.0,
        "verdict_accuracy_on_found": verdict_ok / matched_gold if matched_gold else 0.0,
        "verdict_correct": verdict_ok, "details": details,
    }


def calibration(rows: list[dict]) -> list[dict]:
    out = []
    for label in ("High", "Medium", "Low"):
        group = [r for r in rows if r["confidence_label"] == label]
        out.append({"label": label, "n": len(group),
                    "accuracy": sum(r["correct"] for r in group) / len(group) if group else None})
    return out


def sensitivity(pipeline: ProofreadPipeline, tests: list[dict]) -> list[dict]:
    """Accuracy at different relevance thresholds (not used to choose the default)."""
    original, out = config.RELEVANCE_THRESHOLD, []
    for threshold in (0.35, 0.45, 0.55, 0.65):
        config.RELEVANCE_THRESHOLD = threshold
        predicted = [pipeline.verify(t["claim"], t["collection_id"], options=FAST)["verdict"] for t in tests]
        m = metrics([t["expected_verdict"] for t in tests], predicted)
        m.pop("per_class")
        out.append({"threshold": threshold, **m})
    config.RELEVANCE_THRESHOLD = original
    return out


def group_scores(rows: list[dict], key: str) -> dict:
    """Accuracy per topic or per split."""
    out = {}
    for g in sorted({r[key] for r in rows}):
        sub = [r for r in rows if r[key] == g]
        correct = sum(r["correct"] for r in sub)
        out[g] = {"n": len(sub), "correct": correct, "accuracy": correct / len(sub)}
    return out


# ------------------------------------------------------------------ report
def pct(x) -> str:
    return "n/a" if x is None else f"{x:.0%}"


def write_report(s: dict) -> str:
    f = s["full"]
    md = [
        "# Proofread evaluation report", "",
        f"Generated {s['generated']}. {f['n']} test claims across {len(s['by_topic'])} topics; "
        f"{s['multi']['posts']} multi-claim posts. Settings: relevance threshold {config.RELEVANCE_THRESHOLD}, "
        f"top_k {config.TOP_K}, entailment/contradiction threshold {config.ENTAILMENT_THRESHOLD}/"
        f"{config.CONTRADICTION_THRESHOLD}, mismatch nudge {config.MISMATCH_NUDGE}.", "",
        "## Headline results (full system)", "",
        f"- **Accuracy: {f['correct']}/{f['n']} = {pct(f['accuracy'])}** (macro-F1 {f['macro_f1']:.2f})",
        "- All test claims were seen while the system was being built (there is no held-out set), so this is an optimistic estimate.",
        f"- Not-covered claims wrongly called false: **{pct(f['false_contradiction_rate'])}** (the assignment's key rule)",
        f"- Wrong or not-covered claims wrongly supported: **{pct(f['false_support_rate'])}**",
        f"- Sent to a human as CONFLICTING: {pct(f['sent_to_human_rate'])}",
        f"- End-to-end (claim extracted from the post): {pct(s['e2e']['accuracy'])}; extraction found the intended claim in "
        f"{s['extraction']['found']}/{f['n']} posts",
        f"- Multi-claim posts: found {pct(s['multi']['claim_recall'])} of the claims (precision {pct(s['multi']['claim_precision'])}); "
        f"verdict correct for {pct(s['multi']['verdict_accuracy_on_found'])} of the claims found",
        f"- Average time per claim: {s['speed']['mean_seconds']:.2f} s on {s['device']}", "",
        "## Baselines and ablations", "",
        "| system | type | accuracy | macro-F1 | not-covered → false | wrongly supported | to human |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in s["systems"].items():
        md.append(f"| {name} | {r['group']} | {pct(r['accuracy'])} | {r['macro_f1']:.2f} | {pct(r['false_contradiction_rate'])} "
                  f"| {pct(r['false_support_rate'])} | {pct(r['sent_to_human_rate'])} |")
    md += ["", "What each row means:", ""] + [f"- **{n}**: {r['description']}" for n, r in s["systems"].items()]
    md += ["", "## Accuracy by topic", "", "| topic | accuracy |", "|---|---|"]
    md += [f"| {t} | {r['correct']}/{r['n']} = {pct(r['accuracy'])} |" for t, r in s["by_topic"].items()]
    md += ["", "## Per-class metrics (full system)", "", "| class | precision | recall | F1 | support |", "|---|---|---|---|---|"]
    md += [f"| {c} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | {v['support']} |" for c, v in f["per_class"].items()]
    short = {SUPPORTED: "SUP", CONTRADICTED: "CON", INSUFFICIENT: "INS", CONFLICTING: "CNF"}
    md += ["", "## Confusion matrix (full system)", "", "| expected \\ predicted | " + " | ".join(short[v] for v in VERDICTS) + " |",
           "|---|" + "---|" * len(VERDICTS)]
    md += [f"| {e} | " + " | ".join(str(s["confusion"][e][p]) for p in VERDICTS) + " |" for e in LABELS]
    md += ["", "## Confidence calibration", "", "Is the system right more often when it says High?", "",
           "| confidence | claims | accuracy |", "|---|---|---|"]
    md += [f"| {c['label']} | {c['n']} | {pct(c['accuracy'])} |" for c in s["calibration"]]
    md += ["", "## Relevance-threshold sensitivity", "", "| threshold | accuracy | not-covered → false |", "|---|---|---|"]
    md += [f"| {r['threshold']} | {pct(r['accuracy'])} | {pct(r['false_contradiction_rate'])} |" for r in s["sensitivity"]]
    md += ["", "## Multi-claim posts", ""]
    for d in s["multi"]["details"]:
        md.append(f"- **{d['id']}** ({d['topic']})")
        for p in d["pairs"]:
            got = f"found → {p['predicted']}" if p["extracted"] else "NOT FOUND"
            mark = "✅" if p["predicted"] == p["expected"] else "❌"
            md.append(f"  - {mark} “{p['gold']}” expected {p['expected']}, {got}")
        for extra in d["extra_claims"]:
            md.append(f"  - ➕ extra sentence treated as a claim: “{extra}”")
    md += ["", "## Per-claim results (full system)", "",
           "| id | claim | expected | predicted | confidence | top passage |", "|---|---|---|---|---|---|"]
    for r in s["rows"]:
        conf = f"{r['confidence']:.2f} ({r['confidence_label']})" if r["confidence"] is not None else "– (Low)"
        md.append(f"| {r['id']} | {r['claim']} | {r['expected']} | {'✅' if r['correct'] else '❌'} {r['predicted']} "
                  f"| {conf} | {r['top_passage']} |")
    md += ["", "## Failures", ""]
    failures = [r for r in s["rows"] if not r["correct"]]
    md += [f"- **{r['id']}** “{r['claim']}”: expected {r['expected']}, got {r['predicted']}. "
           f"Stances: {r['stances']}. Note: {r['note']}" for r in failures] or ["None."]
    misses = [r for r in s["rows"] if r["extraction"] == "wrong"]
    if misses:
        md += ["", "### Extraction misses", ""]
        md += [f"- **{r['id']}** picked “{r['extracted_claim']}” instead of “{r['claim']}”" for r in misses]
    md += ["", "_Caveats: 14 hand-written claims is a small test set, and they guided several design decisions "
           "(see the README), so these numbers are optimistic. Accuracy on real social media posts and on other "
           "topics has not been measured._"]
    return "\n".join(md)


def run_evaluation(pipeline: ProofreadPipeline) -> dict:
    """Run every evaluation step, save the result files and return the summary."""
    seed_topics = {c["id"] for c in db.get_collections() if c["origin"] == "seed"}
    tests = [t for t in db.get_test_claims() if t["collection_id"] in seed_topics]
    expected = [t["expected_verdict"] for t in tests]
    print(f"Evaluating {len(tests)} claims on {pipeline.device}...", file=sys.stderr)

    rows = evaluate_full(pipeline, tests)
    predicted = [r["predicted"] for r in rows]

    systems = {}
    for name, (group, description, fn) in Systems(pipeline).all().items():
        print(f"  {name}", file=sys.stderr)
        preds = predicted if name == "Proofread (full)" else [fn(t["claim"], t["collection_id"]) for t in tests]
        m = metrics(expected, preds)
        m.pop("per_class")
        systems[name] = {"group": group, "description": description, **m}

    summary = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "device": pipeline.device,
        "settings": {"relevance_threshold": config.RELEVANCE_THRESHOLD, "top_k": config.TOP_K,
                     "entailment_threshold": config.ENTAILMENT_THRESHOLD,
                     "contradiction_threshold": config.CONTRADICTION_THRESHOLD, "mismatch_nudge": config.MISMATCH_NUDGE},
        "full": metrics(expected, predicted),
        "by_topic": group_scores(rows, "topic"),
        "confusion": confusion(expected, predicted),
        "calibration": calibration(rows),
        "e2e": metrics(expected, [r["predicted_e2e"] for r in rows]),
        "extraction": {"found": sum(r["extraction"] != "wrong" for r in rows),
                       "exact": sum(r["extraction"] == "exact" for r in rows)},
        "speed": {"mean_seconds": sum(r["seconds"] for r in rows) / len(rows)},
        "systems": systems,
        "multi": evaluate_multi(pipeline),
        "sensitivity": sensitivity(pipeline, tests),
        "rows": rows,
    }

    config.RESULTS_DIR.mkdir(exist_ok=True)
    (config.RESULTS_DIR / "eval_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(config.RESULTS_DIR / "eval_results.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (config.RESULTS_DIR / "eval_report.md").write_text(write_report(summary), encoding="utf-8")
    return summary


def main():
    print("Loading models...", file=sys.stderr)
    summary = run_evaluation(ProofreadPipeline())
    systems, rows = summary["systems"], summary["rows"]

    f = summary["full"]
    print("\n" + "=" * 78)
    print(f"Full system accuracy:   {f['correct']}/{f['n']} = {f['accuracy']:.0%}   (macro-F1 {f['macro_f1']:.2f})")
    print(f"Not covered -> 'false': {f['false_contradiction_rate']:.0%}    wrongly supported: {f['false_support_rate']:.0%}")
    m = summary["multi"]
    print(f"Multi-claim: recall {m['claim_recall']:.0%}, precision {m['claim_precision']:.0%}, verdicts {m['verdict_accuracy_on_found']:.0%}")
    print("-" * 78)
    for name, r in systems.items():
        print(f"{name:<24} acc {r['accuracy']:>4.0%}  F1 {r['macro_f1']:.2f}  not-covered->false {r['false_contradiction_rate']:>4.0%}"
              f"  wrongly supported {r['false_support_rate']:>4.0%}")
    print("-" * 78)
    for r in rows:
        if not r["correct"]:
            print(f"FAIL {r['id']:<4} expected {r['expected']:<22} got {r['predicted']:<22} {r['claim'][:38]}")
    print("=" * 78)
    print(f"Saved {config.RESULTS_DIR}/eval_summary.json, eval_results.csv and eval_report.md")


if __name__ == "__main__":
    main()
