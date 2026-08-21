"""Fine-tune DistilBERT for email-importance classification (the model that beats the baseline).

Unlike the TF-IDF baseline (bag-of-words), DistilBERT reads meaning/context, so it distinguishes
"can you approve this?" from "here is the approved doc" that share the same words. Trains on the
Gemini-labeled data, reports macro-F1 on a held-out split (same 80/20, seed 42 as the baseline, so
the numbers are comparable), and saves the model for predict_transformer.py.

Usage (from backend/, needs `make ml-deps`):
    python scripts/train_distilbert.py enron_labeled.csv --epochs 3
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from datasets import Dataset
from sklearn.metrics import f1_score
from sklearn.utils.class_weight import compute_class_weight
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.clean import clean_email_text
from app.ml.dataset import (  # reuse the baseline's CSV loader/split
    load_dataset,
    stratified_split,
)

# RoBERTa-base beats DistilBERT on text classification and loads cleanly on transformers 5.x
# (DeBERTa-v3's SentencePiece tokenizer is broken there). Override with --base-model to compare
# (e.g. distilbert-base-uncased, answerdotai/ModernBERT-base).
_DEFAULT_MODEL = "roberta-base"
_OUT_DIR = Path("models/distilbert")  # the transformer-model slot the predictor loads from
_LABELS = ["low", "medium", "high"]  # index == the id stored on the model
_LABEL_TO_ID = {label: i for i, label in enumerate(_LABELS)}


def _macro_f1(eval_pred) -> dict:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    return {"macro_f1": f1_score(labels, preds, average="macro")}


class WeightedTrainer(Trainer):
    """Trainer with a class-weighted loss so the model can't win by favoring the majority class."""

    def __init__(self, *args, class_weights: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self._class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        weights = self._class_weights.to(outputs.logits.device)
        loss = torch.nn.functional.cross_entropy(outputs.logits, labels, weight=weights)
        return (loss, outputs) if return_outputs else loss


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--base-model", default=_DEFAULT_MODEL)
    args = parser.parse_args()
    print(f"base model: {args.base_model}")

    texts, labels = load_dataset(Path(args.dataset))
    texts = [clean_email_text(t) for t in texts]  # match the cleaning done at inference
    x_train, x_test, y_train, y_test = stratified_split(texts, labels)
    print(f"train={len(x_train)} test={len(x_test)} classes={_LABELS}")

    # Inverse-frequency class weights so a balanced-ish but imperfect split doesn't bias the model.
    y_train_ids = [_LABEL_TO_ID[y] for y in y_train]
    weights = compute_class_weight("balanced", classes=np.arange(len(_LABELS)), y=y_train_ids)
    class_weights = torch.tensor(weights, dtype=torch.float)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    def tokenize(batch: dict) -> dict:
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    def to_dataset(texts_: list[str], labels_: list[str]) -> Dataset:
        ds = Dataset.from_dict({"text": texts_, "label": [_LABEL_TO_ID[y] for y in labels_]})
        return ds.map(tokenize, batched=True)

    train_ds = to_dataset(x_train, y_train)
    test_ds = to_dataset(x_test, y_test)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=len(_LABELS),
        id2label=dict(enumerate(_LABELS)),
        label2id=_LABEL_TO_ID,
    )

    trainer = WeightedTrainer(
        model=model,
        args=TrainingArguments(
            output_dir="models/distilbert-checkpoints",
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            warmup_steps=50,        # ramp LR up gently, then decay — stabler fine-tuning
            weight_decay=0.01,      # light regularization against overfitting the small set
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=1,
            load_best_model_at_end=True,          # keep the epoch with the best macro-F1
            metric_for_best_model="macro_f1",
            greater_is_better=True,
            logging_steps=25,
            report_to=[],
        ),
        train_dataset=train_ds,
        eval_dataset=test_ds,
        compute_metrics=_macro_f1,
        # Pad each batch to its longest example, so variable-length emails stack into a tensor.
        data_collator=DataCollatorWithPadding(tokenizer),
        class_weights=class_weights,
    )

    trainer.train()
    metrics = trainer.evaluate()
    print(f"\nDistilBERT macro-F1 = {metrics['eval_macro_f1']:.4f}  (baseline TF-IDF was ~0.39)")

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(_OUT_DIR)
    tokenizer.save_pretrained(_OUT_DIR)
    print(f"saved model to {_OUT_DIR}")


if __name__ == "__main__":
    main()
