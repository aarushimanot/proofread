"""
Central configuration for Proofread.

Every threshold the pipeline uses lives here so it can be explained (and changed)
in one place. Values can also be overridden with environment variables, e.g.
    PROOFREAD_RELEVANCE_THRESHOLD=0.5 uvicorn app.main:app
"""
import os
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back to a default."""
    return float(os.getenv(name, default))


# ---------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent.parent          # .../backend
DATA_DIR = BASE_DIR / "data"
TOPICS_DIR = DATA_DIR / "topics"                            # one JSON file per built-in topic
TEST_CLAIMS_PATH = DATA_DIR / "test_claims.json"
MULTI_CLAIM_TESTS_PATH = DATA_DIR / "multi_claim_tests.json"
DB_PATH = Path(os.getenv("PROOFREAD_DB", DATA_DIR / "proofread.db"))  # SQLite database file
RESULTS_DIR = BASE_DIR / "results"
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"     # built UI, served by FastAPI

# ---------------------------------------------------------------- models
SPACY_MODEL = "en_core_web_sm"                              # sentence split + NER
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # retrieval
NLI_MODEL = "cross-encoder/nli-deberta-v3-small"            # stance (entail / contradict / neutral)

# ---------------------------------------------------------------- retrieval
TOP_K = int(os.getenv("PROOFREAD_TOP_K", 3))
# Cosine similarity a passage needs before we treat it as "relevant" and run NLI on it.
RELEVANCE_THRESHOLD = _env_float("PROOFREAD_RELEVANCE_THRESHOLD", 0.45)

# ---------------------------------------------------------------- stance
# A passage "supports" / "contradicts" only if the NLI probability clears these.
ENTAILMENT_THRESHOLD = _env_float("PROOFREAD_ENTAILMENT_THRESHOLD", 0.6)
CONTRADICTION_THRESHOLD = _env_float("PROOFREAD_CONTRADICTION_THRESHOLD", 0.6)

# Numeric/date mismatch heuristic: when a relevant passage talks about the same
# thing (shared anchor word, e.g. "landed") but gives a different number/date,
# we move this much probability mass towards "contradiction". It is a nudge,
# not an override: on its own it cannot push a passage past the 0.6 threshold.
MISMATCH_NUDGE = _env_float("PROOFREAD_MISMATCH_NUDGE", 0.35)

# ---------------------------------------------------------------- confidence labels
CONFIDENCE_HIGH = 0.85     # >= High
CONFIDENCE_MEDIUM = 0.70   # >= Medium, otherwise Low

# ---------------------------------------------------------------- extraction
MIN_CLAIM_TOKENS = 5       # sentences shorter than this (in words) are discarded
# Multi-claim mode: a kept sentence counts as a separate claim if it scores at least
# this much (i.e. it names at least one entity/date/number), up to this many per post.
MIN_MULTI_CLAIM_SCORE = 2.0
MAX_CLAIMS_PER_POST = 6

# ---------------------------------------------------------------- API
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

DISCLAIMER = (
    "Proofread is a decision-support tool for human reviewers. The verdict is based only "
    "on a small curated set of reference passages, not on general knowledge, and it may be "
    "wrong. INSUFFICIENT EVIDENCE means the references do not settle the claim; it does NOT "
    "mean the claim is false. A human reviewer should make the final call."
)


def use_cached_models_offline() -> None:
    """
    If both Hugging Face models are already downloaded, tell the libraries not to
    contact the internet. Otherwise they check for updates at every start, which took
    ~2 minutes on a slow connection (vs ~4 s offline), and would hang with no wifi.
    The first run on a new machine still downloads the models normally.
    """
    home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
    hub = Path(os.getenv("HF_HUB_CACHE", home / "hub"))
    if all((hub / ("models--" + m.replace("/", "--"))).is_dir() for m in (EMBEDDING_MODEL, NLI_MODEL)):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")


def pick_device() -> str:
    """Use Apple's GPU (MPS) when available, otherwise CPU."""
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
