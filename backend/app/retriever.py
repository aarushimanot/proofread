"""
Retrieval: find the reference passages most similar in meaning to the claim.

We embed every passage once at startup with the sentence-transformers model
all-MiniLM-L6-v2. For each claim we embed the claim, compute cosine similarity
with every passage, and return the top-k. Embeddings are L2-normalised, so the
cosine similarity is simply a dot product.

Similarity tells us whether a passage is *about* the same thing. It does NOT
tell us whether the passage agrees: that is the job of the NLI step (stance.py).
"""
import numpy as np
from sentence_transformers import SentenceTransformer

from . import config


class Retriever:
    def __init__(self, passages: list[dict], device: str):
        self.passages = passages
        self.model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
        # Embed the passage text only (the same text NLI reads). An earlier version also
        # embedded the title, which pushed the landing passage out of the top 3 for
        # date-heavy claims (see README, "Changes after the first evaluation run").
        texts = [p["text"] for p in passages]
        self.embeddings = self.model.encode(texts, normalize_embeddings=True,
                                            convert_to_numpy=True, show_progress_bar=False)

    def search(self, claim: str, top_k: int = config.TOP_K) -> list[dict]:
        """Return the top_k passages as dicts with an added 'similarity' and 'relevant' flag."""
        query = self.model.encode([claim], normalize_embeddings=True,
                                  convert_to_numpy=True, show_progress_bar=False)[0]
        scores = self.embeddings @ query                    # cosine similarity for every passage
        best = np.argsort(-scores)[:top_k]                  # indices of the highest scores
        results = []
        for idx in best:
            similarity = float(scores[idx])
            results.append({
                **self.passages[idx],
                "similarity": round(similarity, 4),
                "relevant": similarity >= config.RELEVANCE_THRESHOLD,
            })
        return results
