"""
The Proofread pipeline: loads every model once and wires the steps together.

    post text --extract--> claim --retrieve--> top-k passages
              --NLI on relevant passages--> stance per passage
              --number/date check--> (optional nudge)
              --rules--> verdict + explanations

Both the API (main.py) and the evaluation script (evaluate.py) use this class,
so they are guaranteed to behave identically.
"""
import os

# Let PyTorch fall back to CPU for any operation the Apple GPU (MPS) doesn't support.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import spacy  # noqa: E402

from . import config, db  # noqa: E402
from .aggregator import aggregate, apply_mismatch_nudge, passage_stance  # noqa: E402
from .explainer import explain_passage, summarize  # noqa: E402
from .extractor import ClaimExtractor  # noqa: E402
from .retriever import Retriever  # noqa: E402
from .stance import StanceClassifier  # noqa: E402
from .textutils import (claim_predicates, compare_quantities, content_keys,  # noqa: E402
                        extract_quantities, lemma_keys)


class ProofreadPipeline:
    def __init__(self):
        self.device = config.pick_device()
        db.init_db()                      # create tables + load the curated JSON into SQLite
        self.references = db.get_passages()
        self.nlp = spacy.load(config.SPACY_MODEL)
        self.extractor = ClaimExtractor(self.nlp)
        self.retriever = Retriever(self.references, self.device)
        self.stance = StanceClassifier(self.device)

    # ------------------------------------------------------------- extraction
    def extract(self, post_text: str) -> dict:
        return self.extractor.extract(post_text)

    # ------------------------------------------------------------- verification
    def verify(self, claim: str, top_k: int | None = None) -> dict:
        claim = claim.strip()
        claim_doc = self.nlp(claim)
        claim_keys = content_keys(claim_doc)
        claim_quantities = extract_quantities(claim_doc)

        hits = self.retriever.search(claim, top_k or config.TOP_K)

        # Run NLI only on passages that cleared the relevance threshold.
        relevant_hits = [h for h in hits if h["relevant"]]
        nli = self.stance.predict([h["text"] for h in relevant_hits], claim)
        nli_by_id = {h["id"]: probs for h, probs in zip(relevant_hits, nli)}

        evidence = []
        for hit in hits:
            passage_doc = self.nlp(hit["text"])
            passage_keys = content_keys(passage_doc)
            # Shared terms, reported with the passage's own wording so the UI can highlight them.
            matched_terms = [passage_keys[k] for k in passage_keys if k in claim_keys]
            number_matches, mismatches = compare_quantities(claim_quantities, extract_quantities(passage_doc))

            item = {
                "id": hit["id"], "title": hit["title"], "source": hit["source"], "url": hit["url"],
                "date": hit["date"], "text": hit["text"], "similarity": hit["similarity"],
                "relevant": hit["relevant"], "matched_terms": matched_terms,
                "number_matches": number_matches, "mismatches": [],
                "stance": "not_assessed", "probs": None, "raw_probs": None,
                "gated": False, "event_aligned": None, "claim_predicates": [],
            }
            if hit["relevant"]:
                raw = nli_by_id[hit["id"]]
                probs = raw
                # Heuristic: only nudge if the passage also shares non-numeric terms with the claim.
                shares_entities = any(not t[:1].isdigit() for t in matched_terms)
                if mismatches and shares_entities:
                    item["mismatches"] = mismatches
                    probs = apply_mismatch_nudge(raw)
                stance = passage_stance(probs)
                # Heuristic: event-alignment gate. NLI often outputs "contradiction" when the
                # passage simply describes a DIFFERENT event (e.g. "entered lunar orbit on
                # 5 August" vs a claim about the launch date). We only accept a contradiction
                # if the passage uses one of the claim's main verbs or a same-topic number
                # mismatch was found. The gate can remove a contradiction, never create one.
                predicates = claim_predicates(claim_doc)
                aligned = (not predicates or bool(predicates & lemma_keys(passage_doc))
                           or bool(item["mismatches"]))
                if stance == "contradicts" and not aligned:
                    stance = "insufficient"
                    item["gated"] = True
                item.update(raw_probs=raw, probs=probs, stance=stance,
                            event_aligned=aligned, claim_predicates=sorted(predicates))
            item["explanation"] = explain_passage(item)
            evidence.append(item)

        result = aggregate(evidence)
        return {
            "claim": claim,
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "confidence_label": result["confidence_label"],
            "summary": summarize(result["verdict"], evidence),
            "evidence": evidence,
            "thresholds": {
                "relevance": config.RELEVANCE_THRESHOLD,
                "entailment": config.ENTAILMENT_THRESHOLD,
                "contradiction": config.CONTRADICTION_THRESHOLD,
                "mismatch_nudge": config.MISMATCH_NUDGE,
            },
            "disclaimer": config.DISCLAIMER,
        }
