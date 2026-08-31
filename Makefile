# AImail task runner. Deterministic commands only.
# Judgment/generation tasks live as Claude skills in .claude/skills/ instead.

VENV := .venv/bin
.DEFAULT_GOAL := help

.PHONY: help check test lint typecheck hooks dev backend agent web migrate seed ingest eval eval-reform baseline backfill generate ml-deps distilbert eval-classifier label

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-12s %s\n", $$1, $$2}'

check: test lint typecheck  ## backend tests + lint + frontend typecheck

hooks:  ## install git hooks (pre-push runs 'make check')
	git config core.hooksPath .githooks
	@echo "hooks installed — pre-push now runs 'make check' (skip with: git push --no-verify)"

test:  ## backend unit tests
	cd backend && ../$(VENV)/pytest -q

lint:  ## backend lint
	cd backend && ../$(VENV)/ruff check app tests scripts

typecheck:  ## dashboard strict typecheck
	cd frontend/frontend/mail-clarity-dash-main && npx tsc --noEmit

dev:  ## run ALL services (backend, agent, web, listener) in one terminal; Ctrl+C stops all
	./dev.sh

backend:  ## run the backend API on :8000 (frees the port first so restarts never clash)
	-fuser -k 8000/tcp 2>/dev/null
	cd backend && ../$(VENV)/uvicorn app.main:app --reload

agent:  ## run the Lane C email agent on :8001 (frees the port first)
	-fuser -k 8001/tcp 2>/dev/null
	cd backend && ../$(VENV)/uvicorn email_agent:app --reload --port 8001

web:  ## run the dashboard on :8090 (8080 is left to other local projects)
	-fuser -k 8090/tcp 2>/dev/null
	cd frontend/frontend/mail-clarity-dash-main && npm run dev -- --port 8090 --strictPort

migrate:  ## create all tables (RAG + messages + audit_log) — first run
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0001_rag_tables.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0002_messages.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0003_messages_unique.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0004_message_generation.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0005_message_sent.sql

seed:  ## load sample policy chunks
	cd backend && ../$(VENV)/python scripts/seed_demo.py

ingest:  ## ingest a policy PDF: make ingest PDF=path.pdf TITLE="Name"
	cd backend && ../$(VENV)/python scripts/ingest.py "$(PDF)" "$(TITLE)"

eval:  ## retrieval eval, S3 baseline
	cd backend && ../$(VENV)/python scripts/eval_retrieval.py scripts/eval_set.json

eval-reform:  ## retrieval eval with query reformulation (S5)
	cd backend && ../$(VENV)/python scripts/eval_retrieval.py scripts/eval_set.json --reformulate

TEXT ?= text
LABEL ?= label
baseline:  ## train classifier baseline: make baseline DATASET=path.csv [TEXT=col LABEL=col]
	cd backend && ../$(VENV)/python scripts/train_baseline.py "$(DATASET)" --text-col "$(TEXT)" --label-col "$(LABEL)"

backfill:  ## predict + store importance for messages (needs a trained model from `make baseline`)
	cd backend && ../$(VENV)/python scripts/backfill_importance.py

label:  ## hand-label the holdout interactively (one keypress per email): make label HOLDOUT=holdout_to_label.csv
	cd backend && ../$(VENV)/python scripts/label_interactive.py "$(HOLDOUT)"

eval-classifier:  ## grade the classifier on your hand-labeled holdout: make eval-classifier HOLDOUT=holdout_to_label.csv
	cd backend && ../$(VENV)/python scripts/eval_classifier.py "$(HOLDOUT)"

ml-deps:  ## install the heavy DistilBERT training deps (torch/transformers/datasets)
	$(VENV)/pip install -r backend/requirements-ml.txt

distilbert:  ## fine-tune DistilBERT: make distilbert DATASET=enron_labeled.csv [EPOCHS=3]
	cd backend && ../$(VENV)/python scripts/train_distilbert.py "$(DATASET)" --epochs $(or $(EPOCHS),3)

generate:  ## pre-generate drafts for pending messages so opening them is instant (needs make agent)
	cd backend && ../$(VENV)/python scripts/generate_pending.py
