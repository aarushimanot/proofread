"""
Download the two Hugging Face models ahead of time.

Used while building the Docker image so the deployed website starts quickly and never
needs to download anything at runtime. Locally you don't need this: the models are
downloaded automatically the first time the app starts.
"""
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app import config

print(f"Downloading {config.EMBEDDING_MODEL} ...")
SentenceTransformer(config.EMBEDDING_MODEL, device="cpu")
print(f"Downloading {config.NLI_MODEL} ...")
AutoTokenizer.from_pretrained(config.NLI_MODEL)
AutoModelForSequenceClassification.from_pretrained(config.NLI_MODEL)
print("Models ready.")
