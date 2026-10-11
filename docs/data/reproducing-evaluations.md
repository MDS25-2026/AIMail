# Reproducing the evaluation figures

How each figure the project reports can be rebuilt: what goes in, the command, what comes out, and
whether the inputs are in git or must be obtained.

All commands run from `backend/` with the repository's virtual environment at the repo root
(`../.venv/bin/python`), which is what the Makefile's targets do (`VENV := .venv/bin`). Commands that
call Gemini need `GOOGLE_API_KEY` in the repo-root `.env`; commands that touch the database need
`DATABASE_URL`.

**Some commands overwrite tracked files.** They are marked below. Run them on a branch, and compare
with `git diff` before keeping anything.

## Summary

| Figure | Value | Inputs in git? | Rebuild offline? |
|--------|-------|----------------|------------------|
| Category classifier, macro-F1 on the human-audited gold set | 0.8435 (gate 0.85, not met) | Yes | Yes |
| Category classifier, validation macro-F1 on synthetic data | 0.9917 | Yes | Yes |
| Priority classifier, best macro-F1 / accuracy on the human holdout | 0.69 / 70% (target 80%) | No | No: the Enron corpus and labelled CSVs must be obtained |
| Review gate on planted-failure drafts | printed per run | Yes (`eval/critic/v1.json`) | No: needs Presidio and a model |
| Critic confidence over real emails | figures in `specs/features/critic-evaluation-gates.md` | No | No |
| Retrieval hit rate, F1 and cutoffs | `app/rag/cutoffs.json`; `specs/features/rag-retrieval.md` | Sets and scores yes, corpora no | The CI check replays recorded scores offline |
| Local model baseline | `specs/features/local-model.md` | No (`~/llm-lab`, outside the repo) | No |

## 1. Category classifier (6 categories)

Spec: [`../../specs/features/category-classifier.md`](../../specs/features/category-classifier.md).

**Inputs (all in git):**
- `backend/data/category/train.csv`: 600 synthetic emails, 100 per category, generated with Gemini
  in masked form.
- `backend/data/category/holdout_audit.csv`: the blind three-way human audit sheet;
  `AUDIT_GUIDE.md` beside it explains the labelling.
- `backend/data/category/holdout_gold.csv`: the reconciled human gold set, 120 emails.
- `backend/data/category/real_test.csv`: a further test set, evaluated separately.
- `backend/models/category-classifier.joblib`: the trained model that ships.

**Rebuild the reported figure** (evaluate the committed model on the gold set):

```bash
../.venv/bin/python scripts/eval_category_classifier.py
```

Writes `results/category_metrics.json` (macro-F1, per-class report, confusion matrix, CPU latency,
gate verdicts) and `results/category_confusion_matrix.png`. With another CSV, the outputs take its
name as a suffix, for example `scripts/eval_category_classifier.py data/category/real_test.csv`
writes `results/category_metrics_real_test.json`. Both results files are tracked
(`!backend/results/category*` in `.gitignore`), so in a clean rerun the JSON should differ only in
its timestamp and latency; the PNG may differ byte for byte even when the matrix is the same.

**Retrain** (overwrites the tracked `models/category-classifier.joblib` and
`results/category-validation-metrics.json`):

```bash
../.venv/bin/python scripts/train_category_classifier.py   # default data/category/train.csv
```

It uses a stratified 80/20 split and 5-fold cross-validation, both with `random_state=42`, and
reports the validation macro-F1 (0.9917) and the cross-validation mean. These are measured on
synthetic data and are not the headline figure.

**Rebuild the gold set from the audit** (overwrites the tracked `holdout_gold.csv`, then runs the
evaluation above):

```bash
../.venv/bin/python scripts/reconcile_category_audit.py
```

It checks that every auditor's rows are complete, computes pairwise Cohen's kappa on the shared
calibration rows, and writes the reconciled labels.

**Do not rerun `scripts/generate_category_dataset.py`** to reproduce a figure. It asks Gemini for
new emails and overwrites `train.csv`, `holdout_gold.csv` and `holdout_audit.csv`, replacing the
human audit with an unaudited sheet. It is the record of how the data was made, not a step in
reproducing the results; Gemini's output is not deterministic.

## 2. Priority classifier (LOW / MEDIUM / HIGH)

Method and results: [`../../AI_DOCS/priority-classifier.md`](../../AI_DOCS/priority-classifier.md).
Target: [`../../specs/features/priority-classifier.md`](../../specs/features/priority-classifier.md)
(at least 80% agreement with human labels).

**Inputs (not in git; `.gitignore` excludes `backend/*.csv` and `backend/models/*`):**
- The public Enron email corpus (Kaggle `emails.csv`, or its zip). Must be downloaded.
- The Gemini-labelled training set (about 959 emails) produced by `label_dataset.py`.
- The 120-email hand-labelled holdout produced by `sample_holdout.py` and labelled by a person.

The labelled CSVs from the reported runs are not in the repository. Without them, the steps below
rebuild the method, not the exact figures: Gemini labels will differ, and the holdout must be
labelled again by hand.

**Steps:**

```bash
# training labels from Gemini (needs GOOGLE_API_KEY)
../.venv/bin/python scripts/label_dataset.py <emails.csv|archive.zip> --limit 1500 --out enron_labeled.csv
# disjoint holdout (every 300th email from offset 150; training takes offset 0)
../.venv/bin/python scripts/sample_holdout.py <emails.csv|archive.zip> --limit 120 --out holdout_to_label.csv
# hand-label it, one keypress per email
../.venv/bin/python scripts/label_interactive.py holdout_to_label.csv
# baseline: TF-IDF + logistic regression
../.venv/bin/python scripts/train_baseline.py enron_labeled.csv --text-col text --label-col label
# transformer (install requirements-ml.txt first: make ml-deps)
../.venv/bin/python scripts/train_distilbert.py enron_labeled.csv --epochs 5
# grade against the human labels; PRIORITY_MODEL=baseline|distilbert picks the model
PRIORITY_MODEL=distilbert ../.venv/bin/python scripts/eval_classifier.py holdout_to_label.csv
```

**Outputs:**
- `train_baseline.py`: `results/baseline-metrics.json` (macro-F1 on its own split; not tracked) and
  `models/priority-baseline.joblib`.
- `train_distilbert.py`: `models/distilbert/`. Despite the name, its default base model is
  `roberta-base` (`_DEFAULT_MODEL`), the winning configuration, with a 512-token window and
  learning rate 2e-5.
- `eval_classifier.py`: prints macro-F1, the per-class report and the confusion matrix; it writes no
  file, so record the printout.
- `scripts/label_agreement.py <human.csv> <gemini.csv>`: agreement and kappa between human and
  Gemini labels (the 47.9% / kappa 0.22 diagnostic).

**Epochs differ by entry point.** The script defaults to 5 and `AI_DOCS/priority-classifier.md`
reports 5; `make distilbert` passes `--epochs 3` unless `EPOCHS` is set. Use 5 to match the report.

## 3. Critic and review gate

Two different measurements.

**Planted-failure set** (inputs in git: `backend/eval/critic/v1.json`, drafts in English, Malay and
Chinese, each with one planted failure or none, grounded on the fictional Lumora Works handbook):

```bash
../.venv/bin/python scripts/eval_critic_set.py                    # Gemini
../.venv/bin/python scripts/eval_critic_set.py --provider local   # Private mode model
```

Needs Presidio running and the chosen model reachable. Prints, per case, whether the gate flagged
it, the confidence and which check caught it, plus precision and recall overall and per failure.
It writes no file. The deterministic part (the figures check) is replayed offline in
`tests/test_critic_eval_set.py`, which runs in `make check`.

**Critic confidence over real emails** (the figures in
[`../../specs/features/critic-evaluation-gates.md`](../../specs/features/critic-evaluation-gates.md)):

```bash
../.venv/bin/python scripts/eval_critic.py holdout_to_label.csv --limit 20 --out critic_eval.csv
../.venv/bin/python scripts/eval_critic.py holdout_to_label.csv --summary-only --out critic_eval.csv
```

Needs the Lane C agent running on :8001 (`make agent`) and the priority holdout CSV, which is not
in git (section 2). The run is resumable: rows already in the output are skipped. Output CSVs are
gitignored. `make eval-critic [N=20]` runs the first form.

Neither measurement compares the critic with human judgement of whole drafts; see
[`../known-issues.md`](../known-issues.md).

## 4. Retrieval

Spec and recorded results: [`../../specs/features/rag-retrieval.md`](../../specs/features/rag-retrieval.md).

**Inputs:**
- `backend/eval/retrieval/v0.json`: English questions on the HLIB and Genting codes of conduct. In
  git. The PDFs are not (third-party copyright); download them from the URLs in
  `backend/data/policies/README.md`.
- `backend/eval/retrieval/v1.json`: questions in English, Malay and Chinese on the fictional
  "Lumora Works Employee Handbook 2026.pdf". In git. **The handbook PDF is not in the repository**
  (only a short excerpt in `tests/test_chunk.py`); it must be obtained from the team.
- Recorded scores, no text: `v0.gemini.scores.json`, `v1.local.scores.json`. In git.
- The chosen cutoffs: `backend/app/rag/cutoffs.json` (Gemini 0.92 on v0, local 0.88 on v1, both
  calibrated 2026-10-08). In git.

**Offline check (no database, no model):** `tests/test_retrieval_calibration.py` replays the
recorded scores and fails if the committed cutoff differs from what the scores support or the hit
rate falls below 0.9. It runs in `make check`.

**Live rerun:**

```bash
# ingest the corpus; scripts/ingest.py stores it unowned
../.venv/bin/python scripts/ingest.py data/policies/hlib-code-of-conduct.pdf "HLIB Code of Conduct and Ethics"
../.venv/bin/python scripts/ingest.py data/policies/genting-code-of-conduct.pdf "Genting Malaysia Code of Conduct and Ethics"
# report at the recorded cutoff (omit --owner to search unowned documents)
../.venv/bin/python scripts/eval_retrieval.py --set eval/retrieval/v0.json
# v1 needs the Lumora handbook ingested instead (not in the repo, see above)
../.venv/bin/python scripts/ingest.py "<path>/Lumora Works Employee Handbook 2026.pdf" "Lumora Works Employee Handbook 2026"
../.venv/bin/python scripts/eval_retrieval.py --set eval/retrieval/v1.json --provider local
```

Use `--owner <uuid>` when the corpus was uploaded through the dashboard by a signed-in user, since
`ingest.py` stores documents without an owner. `--provider local` needs `LOCAL_EMBEDDING_MODEL` on
Ollama. `--reformulate` measures query reformulation.

`--calibrate` (or `make calibrate`) **overwrites the tracked** `eval/retrieval/<set>.<provider>.scores.json`
and `app/rag/cutoffs.json`. Only run it to re-measure on purpose; the CI check then holds the new
cutoff to the new scores.

The default set differs by entry point: `scripts/eval_retrieval.py` defaults to `v1.json`, while
`make eval` and `make calibrate` default to `SET=eval/retrieval/v0.json`.

## 5. Local model baseline

Results: [`../../specs/features/local-model.md`](../../specs/features/local-model.md) (nine masked
emails in English, Malay and Chinese; Gemini 2.5 Flash, Gemma 4 E2B, Qwen2.5 3B and Qwen3 4B; the
critic as a proxy score; then a one-rater blind human pilot).

**Inputs and harness are not in the repository.** They live in `~/llm-lab` on the experimenter's
machine: `benchmark.json`, `compare.py`, `summary.py`, the blind rating page
`rating-template.html` and its key `rating-key.json`. Reproducing the table needs those files from
the experimenter, Ollama with the listed models, and a Gemini key for the critic scores. The
hardware and Ollama version used are recorded in the spec. The human ratings cannot be replayed;
new raters produce new figures.
