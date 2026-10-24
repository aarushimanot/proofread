"""
The Proofread pipeline: loads every model once and wires the steps together.

    post text --extract--> claim(s) --retrieve--> top-k passages of the chosen topic
              --NLI on relevant passages (whole passage + each sentence)--> stance per passage
              --number/date check, event-alignment gate--> adjusted stance
              --rules--> verdict + explanations + the key sentence of each passage

The Streamlit app, the FastAPI server and the evaluation script all use this
class, so they are guaranteed to behave identically.
"""
import os
from dataclasses import dataclass

# Let PyTorch fall back to CPU for any operation the Apple GPU (MPS) doesn't support.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from . import config, db  # noqa: E402

# Must run before the Hugging Face libraries are imported (they read the setting once).
config.use_cached_models_offline()

import spacy  # noqa: E402
from .aggregator import VERDICTS, aggregate, apply_mismatch_nudge, passage_stance  # noqa: E402
from .explainer import explain_passage, summarize  # noqa: E402
from .extractor import ClaimExtractor  # noqa: E402
from .retriever import Retriever  # noqa: E402
from .stance import StanceClassifier  # noqa: E402
from .textutils import (claim_predicates, compare_quantities, content_keys,  # noqa: E402
                        extract_quantities, lemma_keys)


@dataclass(frozen=True)
class VerifyOptions:
    """
    Switches for each part of the pipeline. The defaults are the real system; the
    evaluation turns parts off one at a time (an "ablation study") to measure what
    each part contributes.
    """
    use_relevance_threshold: bool = True   # off: every top-k passage counts as relevant
    use_mismatch_check: bool = True        # heuristic 1: number/date mismatch nudge
    use_event_gate: bool = True            # heuristic 2: ignore contradictions about other events
    sentence_level: bool = False           # judge each passage by its most decisive sentence
    explain: bool = True                   # key sentences + explanations (off = faster evaluation)


DEFAULT_OPTIONS = VerifyOptions()


def _decisiveness(probs: dict) -> float:
    """How strongly a probability triple points to support OR contradiction."""
    return max(probs["entailment"], probs["contradiction"])


class ProofreadPipeline:
    def __init__(self):
        self.device = config.pick_device()
        db.init_db()                      # create tables + load the built-in topics into SQLite
        self.nlp = spacy.load(config.SPACY_MODEL)
        self.extractor = ClaimExtractor(self.nlp)
        self.retriever = Retriever(self.device)
        self.stance = StanceClassifier(self.device)
        self.retriever.embeddings_for(db.get_passages())   # pre-compute embeddings at startup

    # ------------------------------------------------------------- extraction
    def extract(self, post_text: str) -> dict:
        return self.extractor.extract(post_text)

    # ------------------------------------------------------------- verification
    def verify(self, claim: str, collection_id: str | None = None, top_k: int | None = None,
               options: VerifyOptions = DEFAULT_OPTIONS) -> dict:
        """
        Check a claim against the passages of one topic (collection_id), or of all
        topics when collection_id is None. Passages are read fresh from the database,
        so anything added in the app is used immediately.
        """
        claim = claim.strip()
        passages = db.get_passages(collection_id)
        claim_doc = self.nlp(claim)
        claim_keys = content_keys(claim_doc)
        claim_quantities = extract_quantities(claim_doc)
        predicates = claim_predicates(claim_doc)

        hits = self.retriever.search(claim, passages, top_k or config.TOP_K)
        if not options.use_relevance_threshold:
            hits = [{**h, "relevant": True} for h in hits]
        relevant_hits = [h for h in hits if h["relevant"]]
        docs = {h["id"]: self.nlp(h["text"]) for h in hits}

        # NLI on each relevant passage as a whole...
        nli = self.stance.predict([h["text"] for h in relevant_hits], claim)
        passage_probs = {h["id"]: probs for h, probs in zip(relevant_hits, nli)}

        # ...and on each of its sentences, to find the sentence that decides the judgement.
        sentence_probs: dict[str, list] = {}
        if options.explain or options.sentence_level:
            flat = [(h["id"], s.text.strip()) for h in relevant_hits
                    for s in docs[h["id"]].sents if s.text.strip()]
            flat_probs = self.stance.predict([s for _, s in flat], claim)
            for (pid, sent), probs in zip(flat, flat_probs):
                sentence_probs.setdefault(pid, []).append({"text": sent, "probs": probs})

        evidence = []
        for hit in hits:
            passage_doc = docs[hit["id"]]
            passage_keys = content_keys(passage_doc)
            # Shared terms, reported with the passage's own wording so the UI can highlight them.
            matched_terms = [passage_keys[k] for k in passage_keys if k in claim_keys]
            number_matches, mismatches = compare_quantities(claim_quantities, extract_quantities(passage_doc))

            item = {
                "id": hit["id"], "collection_id": hit.get("collection_id"), "title": hit["title"],
                "source": hit["source"], "url": hit["url"], "date": hit["date"], "text": hit["text"],
                "similarity": hit["similarity"], "relevant": hit["relevant"], "matched_terms": matched_terms,
                "number_matches": number_matches, "mismatches": [],
                "stance": "not_assessed", "probs": None, "raw_probs": None,
                "gated": False, "event_aligned": None, "claim_predicates": sorted(predicates),
                "sentences": sentence_probs.get(hit["id"], []), "key_sentence": None, "judged_on": "passage",
            }
            if hit["relevant"]:
                raw = passage_probs[hit["id"]]
                # Sentence-level variant: judge the passage by its most decisive sentence.
                if options.sentence_level and item["sentences"]:
                    best = max(item["sentences"], key=lambda s: _decisiveness(s["probs"]))
                    if _decisiveness(best["probs"]) > _decisiveness(raw):
                        raw, item["judged_on"] = best["probs"], "sentence"
                probs = raw
                # Heuristic 1: only nudge if the passage also shares non-numeric terms with the claim.
                shares_entities = any(not t[:1].isdigit() for t in matched_terms)
                if options.use_mismatch_check and mismatches and shares_entities:
                    item["mismatches"] = mismatches
                    probs = apply_mismatch_nudge(raw)
                stance = passage_stance(probs)
                # Heuristic 2: event-alignment gate. NLI often outputs "contradiction" when the
                # passage simply describes a DIFFERENT event (e.g. "entered lunar orbit on
                # 5 August" vs a claim about the launch date). We only accept a contradiction
                # if the passage uses one of the claim's main event verbs or a same-topic number
                # mismatch was found. The gate can remove a contradiction, never create one.
                aligned = (not predicates or bool(predicates & lemma_keys(passage_doc))
                           or bool(item["mismatches"]))
                if options.use_event_gate and stance == "contradicts" and not aligned:
                    stance = "insufficient"
                    item["gated"] = True
                item.update(raw_probs=raw, probs=probs, stance=stance, event_aligned=aligned)
                item["key_sentence"] = self._key_sentence(item, claim_keys)
            if options.explain:
                item["explanation"] = explain_passage(item)
            evidence.append(item)

        result = aggregate(evidence)
        return {
            "claim": claim,
            "collection_id": collection_id,
            "passages_searched": len(passages),
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "confidence_label": result["confidence_label"],
            "summary": summarize(result["verdict"], evidence, searched=len(passages)),
            "evidence": evidence,
            "thresholds": {
                "relevance": config.RELEVANCE_THRESHOLD,
                "entailment": config.ENTAILMENT_THRESHOLD,
                "contradiction": config.CONTRADICTION_THRESHOLD,
                "mismatch_nudge": config.MISMATCH_NUDGE,
            },
            "disclaimer": config.DISCLAIMER,
        }

    def _key_sentence(self, item: dict, claim_keys: dict) -> int | None:
        """
        Index of the sentence that best explains the passage's stance:
          supports     -> the sentence with the highest entailment
          contradicts  -> the sentence with the highest contradiction
          insufficient -> the most decisive sentence, or else the one sharing most words with the claim
        """
        sents = item["sentences"]
        if not sents:
            return None
        if item["stance"] == "supports":
            return max(range(len(sents)), key=lambda i: sents[i]["probs"]["entailment"])
        if item["stance"] == "contradicts":
            return max(range(len(sents)), key=lambda i: sents[i]["probs"]["contradiction"])
        best = max(range(len(sents)), key=lambda i: _decisiveness(sents[i]["probs"]))
        if _decisiveness(sents[best]["probs"]) >= 0.5:
            return best
        overlap = lambda i: sum(1 for k in content_keys(self.nlp(sents[i]["text"])) if k in claim_keys)  # noqa: E731
        return max(range(len(sents)), key=overlap)

    # ------------------------------------------------------------- multi-claim posts
    def check_post(self, post_text: str, collection_id: str | None = None,
                   options: VerifyOptions = DEFAULT_OPTIONS) -> dict:
        """Find every factual claim in a post and check each one separately."""
        extraction = self.extractor.extract_claims(post_text)
        results = [self.verify(c, collection_id, options=options) for c in extraction["claims"]]
        counts = {v: sum(r["verdict"] == v for r in results) for v in VERDICTS}
        return {"claims": results, "counts": counts, "candidates": extraction["candidates"]}
