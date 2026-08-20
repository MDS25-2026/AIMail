# Priority Classifier — Methodology (Lane B)

How AImail assigns a LOW / MEDIUM / HIGH importance to each incoming email. Written as a reference
for the FYP report; the running code lives in `backend/app/ml/` and `backend/scripts/`.

## Problem

Given the masked text of an email (subject + body), predict how much it needs the recipient's
attention, as a 3-class label: **LOW / MEDIUM / HIGH**. This drives the dashboard's priority badge
and sorting. Timing (deadlines) is handled by a *separate* deterministic layer, not this classifier
(see "Composite priority" below).

## The importance rubric

A single rubric defines the label — it is the ground-truth definition, applied both by the labeling
step and (implicitly) by the model it trains:

- **HIGH** — any of: asks the recipient to reply / decide / approve / do a task; high-stakes
  content (money, contracts, legal, deals, outages, escalations); reads like a directive or request
  from someone in authority.
- **LOW** — any of: automated or bulk (newsletters, notifications, system mail, marketing); purely
  social or logistical (thank-yous, small talk, casual banter).
- **MEDIUM** — everything else: work-relevant and informative, but needs no direct action.

Judged from **content only** — deadlines/dates are deliberately excluded (the temporal layer owns
timing) and sender seniority is left to a future deterministic VIP layer, so the text model learns
language, not org charts.

## Dataset & labeling

- **Source:** the public Enron email corpus (~500k emails; Kaggle `emails.csv`).
- **Sampling:** systematic (every Nth email) so the sample spans many mailboxes rather than one
  sender's folder. Raw RFC-822 messages are parsed to `subject + body`.
- **Labeling — LLM-assisted (documented as such, NOT hand-labeled gold):** each email is labeled by
  Gemini applying the rubric above, batched to stay under API rate limits
  (`backend/scripts/label_dataset.py`). This yields a labeled training set of ~959 emails with a
  balanced distribution (~28% LOW / 38% MEDIUM / 32% HIGH).
- **Honest evaluation set:** a **disjoint** sample is hand-labeled by a human
  (`backend/scripts/sample_holdout.py`, offset from the training stride so there is no leakage).
  Models are graded against these human labels (`backend/scripts/eval_classifier.py`), so reported
  accuracy reflects human judgment, not the LLM's.

**Why LLM-assisted labeling:** hand-labeling thousands of emails is infeasible in the project
timeline; a rubric-driven LLM produces consistent labels at scale. This is a recognized weak-
supervision technique. Its limitation — labels are only as good as the LLM's reading of the rubric —
is controlled for by evaluating on the human-labeled holdout.

## Models

### Baseline — TF-IDF + Logistic Regression

`backend/app/ml/baseline.py`. Bag-of-words: TF-IDF features (uni+bi-grams, English stopwords) into a
class-weight-balanced logistic regression. Fast, interpretable, and the floor the neural model must
beat. Graded on **macro-F1** (not accuracy) because it weights all three classes equally regardless
of imbalance.

**Result:** macro-F1 = **0.39** on the held-out split (per-class F1 ~0.38-0.42). Barely above the
3-class chance level of 0.33 — expected, because importance is about *meaning* (a request vs. a
confirmation share the same words), which bag-of-words cannot see.

### Fine-tuned — DistilBERT

`backend/scripts/train_distilbert.py`. `distilbert-base-uncased` (a distilled BERT: ~40% smaller,
~97% of BERT's performance) with a 3-way classification head, fine-tuned on the labeled set. Unlike
TF-IDF it models meaning and context, so it distinguishes "can you approve this?" from "here is the
approved doc." Trained/evaluated on the **same 80/20 split (seed 42)** as the baseline, so the
macro-F1 numbers are directly comparable.

Selection is config-driven: `PRIORITY_MODEL=baseline|distilbert` chooses which predictor
`backfill_importance.py` uses; the DistilBERT predictor imports torch lazily so the API process
never loads it unless selected.

## Composite priority (text + time)

The final priority combines two independent signals:

1. **Learned importance** — this classifier, from content.
2. **Temporal layer** — `backend/app/ml/temporal.py`, deterministic: extracts a deadline from the
   text and boosts the score the nearer it is. `now` is *injected*, so for historical corpora
   (Enron) urgency is computed relative to the email's own `Date:` header, not the wall clock.

Keeping them separate is deliberate: a date is not learnable from text alone, and baking it into the
training label would make labels unstable.

## Pipeline (commands)

```
label_dataset.py   -> enron_labeled.csv   (make: manual)      # LLM-assisted training labels
sample_holdout.py  -> holdout.csv         (manual hand-label) # honest test set
train_baseline.py  -> priority-baseline.joblib  (make baseline)
train_distilbert.py-> models/distilbert/        (make distilbert)
eval_classifier.py -> macro-F1 vs human labels  (make eval-classifier)
backfill_importance.py -> writes importance onto messages (make backfill)
```

## Limitations & next steps

- Small labeled set (~959) caps the neural model; more labeled data helps DistilBERT far more than
  it helped TF-IDF.
- Labels are LLM-generated; the human holdout is the check, and should be enlarged for a tighter
  confidence interval.
- Sender seniority is not yet modeled — a deterministic VIP-sender layer (like the temporal layer)
  is the intended next signal.
