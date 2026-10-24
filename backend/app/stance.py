"""
Stance detection with Natural Language Inference (NLI).

An NLI model reads a premise and a hypothesis and says whether the premise
ENTAILS the hypothesis, CONTRADICTS it, or is NEUTRAL (neither).
Here: premise = reference passage, hypothesis = the claim.

This is what keeps the verdict grounded in the references: the model is only
asked "does THIS passage support or contradict THIS claim?", never "is the
claim true?".

Model: cross-encoder/nli-deberta-v3-small. We read the label order from the
model's own config (id2label) instead of hard-coding it, because label order
differs between NLI models.
"""
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from . import config

LABELS = ("entailment", "contradiction", "neutral")


class StanceClassifier:
    def __init__(self, device: str):
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(config.NLI_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(config.NLI_MODEL)
        self.model.to(device).eval()

        # e.g. {0: 'contradiction', 1: 'entailment', 2: 'neutral'} for this model.
        id2label = {int(i): label.lower() for i, label in self.model.config.id2label.items()}
        self.label_index = {label: idx for idx, label in id2label.items()}
        if set(self.label_index) != set(LABELS):
            raise ValueError(f"Unexpected NLI labels in model config: {id2label}")

    @torch.inference_mode()
    def predict(self, premises: list[str], hypothesis: str) -> list[dict]:
        """Return one {'entailment', 'contradiction', 'neutral'} probability dict per premise."""
        if not premises:
            return []
        inputs = self.tokenizer(premises, [hypothesis] * len(premises), padding=True,
                                truncation=True, max_length=512, return_tensors="pt").to(self.device)
        logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).cpu().tolist()
        return [{label: round(row[self.label_index[label]], 4) for label in LABELS} for row in probs]
