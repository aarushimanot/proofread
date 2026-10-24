"""
Retrieval: find the reference passages most similar in meaning to the claim.

Each passage is turned into an embedding (a list of numbers capturing its meaning)
with the sentence-transformers model all-MiniLM-L6-v2. For each claim we embed the
claim, compute cosine similarity with every passage of the chosen topic, and return
the top-k. Embeddings are L2-normalised, so cosine similarity is a dot product.

Passages can be added, edited or deleted at any time in the app, so embeddings are
cached per passage and recomputed only when a passage's text changes.

Similarity tells us whether a passage is *about* the same thing. It does NOT
tell us whether the passage agrees: that is the job of the NLI step (stance.py).
"""
import threading

import numpy as np
from sentence_transformers import SentenceTransformer

from . import config


class Retriever:
    def __init__(self, device: str):
        self.model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
        self._cache: dict[str, tuple[str, np.ndarray]] = {}   # passage id -> (text, embedding)
        self._lock = threading.Lock()

    def _embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)

    def embeddings_for(self, passages: list[dict]) -> np.ndarray:
        """Embedding matrix for these passages, computing only new or changed ones."""
        with self._lock:
            # Embed the passage text only (the same text NLI reads). An earlier version also
            # embedded the title, which pushed the landing passage out of the top 3 for
            # date-heavy claims (see README, "Changes after the first evaluation run").
            missing = [p for p in passages if self._cache.get(p["id"], (None,))[0] != p["text"]]
            if missing:
                for p, vec in zip(missing, self._embed([p["text"] for p in missing])):
                    self._cache[p["id"]] = (p["text"], vec)
            return np.stack([self._cache[p["id"]][1] for p in passages])

    def search(self, claim: str, passages: list[dict], top_k: int = config.TOP_K) -> list[dict]:
        """Return the top_k passages as dicts with an added 'similarity' and 'relevant' flag."""
        if not passages:
            return []
        matrix = self.embeddings_for(passages)
        query = self._embed([claim])[0]
        scores = matrix @ query                             # cosine similarity for every passage
        best = np.argsort(-scores)[:top_k]                  # indices of the highest scores
        results = []
        for idx in best:
            similarity = float(scores[idx])
            results.append({
                **passages[idx],
                "similarity": round(similarity, 4),
                "relevant": similarity >= config.RELEVANCE_THRESHOLD,
            })
        return results
