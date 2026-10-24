"""
Evaluate Proofread on the labelled test claims.

    python evaluate.py            # main evaluation
    python evaluate.py --sweep    # also show how results change with threshold / top_k

For every test claim we:
  1. run claim extraction on the post and check whether it found the intended claim;
  2. verify the GOLD claim (measures verification on its own);
  3. verify the EXTRACTED claim (measures the full end-to-end pipeline).

Outputs: results/eval_results.csv and results/eval_report.md, plus a printed summary.
Thresholds are NOT tuned here; failures are reported as they are.
"""
import argparse
import csv
import re
import sys

from app import config, db
from app.aggregator import VERDICTS
from app.pipeline import ProofreadPipeline


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def extraction_status(extracted: str, gold: str) -> str:
    """'exact', 'contains' (gold claim plus extra words), or 'wrong'."""
    e, g = normalise(extracted), normalise(gold)
    if e == g:
        return "exact"
    if g and g in e:
        return "contains"
    return "wrong"


def metrics(rows: list[dict], key: str) -> dict:
    """Accuracy, per-class precision/recall/F1 and a confusion matrix for one prediction column."""
    labels = list(VERDICTS)
    confusion = {exp: {pred: 0 for pred in labels} for exp in labels}
    for r in rows:
        confusion[r["expected"]][r[key]] += 1
    correct = sum(r["expected"] == r[key] for r in rows)
    per_class = {}
    for label in labels:
        tp = confusion[label][label]
        predicted = sum(confusion[exp][label] for exp in labels)
        actual = sum(confusion[label].values())
        precision = tp / predicted if predicted else None
        recall = tp / actual if actual else None
        f1 = (2 * precision * recall / (precision + recall)
              if precision and recall else (0.0 if predicted or actual else None))
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1,
                            "support": actual, "predicted": predicted}
    return {"accuracy": correct / len(rows), "correct": correct, "total": len(rows),
            "per_class": per_class, "confusion": confusion}


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def run(pipeline: ProofreadPipeline, tests: list[dict]) -> list[dict]:
    rows = []
    for t in tests:
        extracted = pipeline.extract(t["post_text"])["claim"]
        gold = pipeline.verify(t["claim"])
        e2e = pipeline.verify(extracted) if extracted else {"verdict": "INSUFFICIENT_EVIDENCE"}
        top = gold["evidence"][0] if gold["evidence"] else None
        rows.append({
            "id": t["id"],
            "claim": t["claim"],
            "expected": t["expected_verdict"],
            "predicted": gold["verdict"],
            "correct": gold["verdict"] == t["expected_verdict"],
            "confidence": gold["confidence"],
            "confidence_label": gold["confidence_label"],
            "top_passage": f"{top['id']} {top['title']}" if top else "",
            "top_similarity": top["similarity"] if top else None,
            "relevant_passages": sum(e["relevant"] for e in gold["evidence"]),
            "stances": "; ".join(f"{e['id']}:{e['stance']}" for e in gold["evidence"]),
            "extracted_claim": extracted,
            "extraction": extraction_status(extracted, t["claim"]),
            "predicted_e2e": e2e["verdict"],
            "note": t["note"],
        })
    return rows


def confusion_md(m: dict) -> str:
    labels = list(VERDICTS)
    short = {"SUPPORTED": "SUP", "CONTRADICTED": "CON", "INSUFFICIENT_EVIDENCE": "INS", "CONFLICTING": "CNF"}
    lines = ["| expected \\ predicted | " + " | ".join(short[l] for l in labels) + " |",
             "|---|" + "---|" * len(labels)]
    for exp in labels:
        lines.append(f"| {exp} | " + " | ".join(str(m["confusion"][exp][p]) for p in labels) + " |")
    return "\n".join(lines)


def per_class_md(m: dict) -> str:
    lines = ["| class | precision | recall | F1 | support | predicted |", "|---|---|---|---|---|---|"]
    for label, s in m["per_class"].items():
        lines.append(f"| {label} | {fmt(s['precision'])} | {fmt(s['recall'])} | {fmt(s['f1'])} "
                     f"| {s['support']} | {s['predicted']} |")
    return "\n".join(lines)


def write_report(rows, m_gold, m_e2e, sweep_md: str) -> str:
    ext_ok = sum(r["extraction"] != "wrong" for r in rows)
    ext_exact = sum(r["extraction"] == "exact" for r in rows)
    failures = [r for r in rows if not r["correct"]]

    md = [
        "# Proofread evaluation report", "",
        f"Test claims: **{len(rows)}**. Settings: relevance threshold {config.RELEVANCE_THRESHOLD}, "
        f"top_k {config.TOP_K}, entailment/contradiction threshold {config.ENTAILMENT_THRESHOLD}/"
        f"{config.CONTRADICTION_THRESHOLD}, mismatch nudge {config.MISMATCH_NUDGE}.", "",
        "## Summary", "",
        f"- Verification accuracy (gold claim): **{m_gold['correct']}/{m_gold['total']} = {m_gold['accuracy']:.0%}**",
        f"- End-to-end accuracy (extracted claim): **{m_e2e['correct']}/{m_e2e['total']} = {m_e2e['accuracy']:.0%}**",
        f"- Extraction found the intended claim: **{ext_ok}/{len(rows)}** "
        f"({ext_exact} exact, {ext_ok - ext_exact} with extra words)", "",
        "## Per-class metrics (gold claim)", "", per_class_md(m_gold), "",
        "## Confusion matrix (gold claim)", "", confusion_md(m_gold), "",
        "## Per-claim results", "",
        "| id | claim | expected | predicted | confidence | top passage | extraction | end-to-end |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        mark = "✅" if r["correct"] else "❌"
        conf = f"{r['confidence']:.2f} ({r['confidence_label']})" if r["confidence"] is not None else "– (Low)"
        md.append(f"| {r['id']} | {r['claim']} | {r['expected']} | {mark} {r['predicted']} | {conf} "
                  f"| {r['top_passage']} | {r['extraction']} | {r['predicted_e2e']} |")
    md += ["", "## Failures", ""]
    if not failures:
        md.append("No failures on this test set. With only 14 claims this does not mean the system is reliable.")
    for r in failures:
        md.append(f"- **{r['id']}** “{r['claim']}”: expected {r['expected']}, got {r['predicted']}. "
                  f"Stances: {r['stances']}. Note: {r['note']}")
    wrong_ext = [r for r in rows if r["extraction"] == "wrong"]
    if wrong_ext:
        md += ["", "### Extraction misses", ""]
        md += [f"- **{r['id']}** picked “{r['extracted_claim']}” instead of “{r['claim']}”"
               for r in wrong_ext]
    if sweep_md:
        md += ["", sweep_md]
    md += ["", "_Caveat: 14 hand-written claims is a tiny test set, and some heuristics were added after "
           "inspecting failures on it, so these numbers are optimistic. Treat them as a sanity check, "
           "not a measure of real-world accuracy._"]
    return "\n".join(md)


def sweep(pipeline: ProofreadPipeline, tests: list[dict]) -> str:
    """Sensitivity analysis: accuracy for different relevance thresholds and top_k values."""
    original = config.RELEVANCE_THRESHOLD
    lines = ["## Sensitivity analysis (gold claim accuracy)", "",
             "Not used to choose the defaults; shown to make threshold sensitivity visible.", "",
             "| relevance threshold | top_k=3 | top_k=5 |", "|---|---|---|"]
    for threshold in (0.35, 0.45, 0.55, 0.65):
        config.RELEVANCE_THRESHOLD = threshold
        cells = []
        for k in (3, 5):
            correct = sum(pipeline.verify(t["claim"], top_k=k)["verdict"] == t["expected_verdict"]
                          for t in tests)
            cells.append(f"{correct}/{len(tests)}")
        lines.append(f"| {threshold} | " + " | ".join(cells) + " |")
    config.RELEVANCE_THRESHOLD = original
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep", action="store_true", help="also run a threshold/top_k sensitivity analysis")
    args = parser.parse_args()

    print("Loading models...", file=sys.stderr)
    pipeline = ProofreadPipeline()            # also syncs the JSON seed files into SQLite
    tests = db.get_test_claims()
    print(f"Evaluating {len(tests)} claims from the database...", file=sys.stderr)
    rows = run(pipeline, tests)
    m_gold, m_e2e = metrics(rows, "predicted"), metrics(rows, "predicted_e2e")
    sweep_md = sweep(pipeline, tests) if args.sweep else ""

    config.RESULTS_DIR.mkdir(exist_ok=True)
    with open(config.RESULTS_DIR / "eval_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    report = write_report(rows, m_gold, m_e2e, sweep_md)
    (config.RESULTS_DIR / "eval_report.md").write_text(report, encoding="utf-8")

    # ---- console summary
    print("\n" + "=" * 72)
    print(f"Verification accuracy (gold claim):   {m_gold['correct']}/{m_gold['total']} = {m_gold['accuracy']:.0%}")
    print(f"End-to-end accuracy (extracted claim): {m_e2e['correct']}/{m_e2e['total']} = {m_e2e['accuracy']:.0%}")
    print(f"Extraction found intended claim:       {sum(r['extraction'] != 'wrong' for r in rows)}/{len(rows)}")
    print("-" * 72)
    for r in rows:
        mark = "OK  " if r["correct"] else "FAIL"
        print(f"{mark} {r['id']}  expected {r['expected']:<22} got {r['predicted']:<22} {r['claim'][:45]}")
    print("-" * 72)
    for label, s in m_gold["per_class"].items():
        print(f"{label:<22} precision {fmt(s['precision'])}  recall {fmt(s['recall'])}  support {s['support']}")
    if sweep_md:
        print("\n" + sweep_md)
    print("=" * 72)
    print(f"Saved {config.RESULTS_DIR / 'eval_results.csv'} and {config.RESULTS_DIR / 'eval_report.md'}")


if __name__ == "__main__":
    main()
