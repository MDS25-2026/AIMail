# AImail task runner. Deterministic commands only.
# Judgment/generation tasks live as Claude skills in .claude/skills/ instead.

VENV := .venv/bin
.DEFAULT_GOAL := help

.PHONY: help check test lint typecheck hooks dev backend agent web test-reader migrate seed ingest eval eval-reform baseline backfill generate ml-deps distilbert eval-classifier label eval-critic latency extension

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-12s %s\n", $$1, $$2}'

check: test lint typecheck  ## backend tests + ruff; dashboard typecheck, eslint, unit tests, palette check

hooks:  ## install git hooks (pre-push runs 'make check')
	git config core.hooksPath .githooks
	@echo "hooks installed — pre-push now runs 'make check' (skip with: git push --no-verify)"

test:  ## backend unit tests
	cd backend && ../$(VENV)/pytest -q

lint:  ## backend lint
	cd backend && ../$(VENV)/ruff check app tests scripts email_agent.py gemini_client.py

typecheck:  ## dashboard typecheck, palette contrast/colour-blind checks, lint and unit tests
	cd frontend/frontend/mail-clarity-dash-main && npx tsc --noEmit
	cd frontend/frontend/mail-clarity-dash-main && python3 scripts/check-palette.py --quiet
	cd frontend/frontend/mail-clarity-dash-main && npx eslint src && npm test --silent

dev:  ## run ALL services (backend, agent, web, listener) in one terminal; Ctrl+C stops all
	./dev.sh

# --no-access-log: app.request already logs each request without its query, which can carry the
# one-time sign-in code (/auth/callback?code=...); uvicorn's own access line prints it.
backend:  ## run the backend API on :8000 (frees the port first so restarts never clash)
	-fuser -k 8000/tcp 2>/dev/null
	cd backend && ../$(VENV)/uvicorn app.main:app --reload --no-access-log

agent:  ## run the Lane C email agent on :8001 (localhost-only; frees the port first)
	-fuser -k 8001/tcp 2>/dev/null
	cd backend && ../$(VENV)/uvicorn email_agent:app --reload --port 8001 --host 127.0.0.1

web:  ## run the dashboard on :8090 (8080 is left to other local projects)
	-fuser -k 8090/tcp 2>/dev/null
	cd frontend/frontend/mail-clarity-dash-main && npm run dev -- --port 8090 --strictPort

extension:  ## build the Chrome extension into extension-dist/ (load unpacked) and aimail-extension.zip
	cd frontend/frontend/mail-clarity-dash-main && npm run build:extension
	cd frontend/frontend/mail-clarity-dash-main/extension-dist && python3 -m zipfile -c ../aimail-extension.zip .

test-reader:  ## attachment reader tests, inside its image against the real OCR and NER models
	docker build -q -t aimail-attachment-reader:test listener/attachment-reader
	docker run --rm --user root --entrypoint sh aimail-attachment-reader:test -c 'pip install -q pytest && python -m pytest -q -p no:warnings tests'

migrate:  ## create all tables; run BEFORE starting a newer listener (it writes masking_status)
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0001_rag_tables.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0002_messages.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0003_messages_unique.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0004_message_generation.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0005_message_sent.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0006_message_read.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0007_personalisation.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0008_critic_attempts.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0009_thread_identity.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0010_critic_checks.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0011_rag_sources.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0012_masking_status.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0013_masking_attempts.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0014_generation_attempts_reply_to.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0015_enable_rls.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0016_mailbox_connection.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0017_owner_scoping.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0018_pii_vault.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0019_holding_reply.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0020_writing_style.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0021_needs_reconnect.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0022_private_mode.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0023_local_embedding.sql
	cd backend && ../$(VENV)/python scripts/apply_migration.py app/db/migrations/0024_sender_auth_and_audit_chain.sql

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

latency:  ## time N drafts end to end and summarise retries and fallbacks: make latency [N=5] (needs `make agent`)
	cd backend && ../$(VENV)/python scripts/latency.py $(or $(HOLDOUT),holdout_to_label.csv) --limit $(or $(N),5)

eval-critic:  ## characterise critic confidence over real emails: make eval-critic [N=20] (needs `make agent` running)
	cd backend && ../$(VENV)/python scripts/eval_critic.py $(or $(HOLDOUT),holdout_to_label.csv) --limit $(or $(N),20)

ml-deps:  ## install the heavy DistilBERT training deps (torch/transformers/datasets)
	$(VENV)/pip install -r backend/requirements-ml.txt

distilbert:  ## fine-tune DistilBERT: make distilbert DATASET=enron_labeled.csv [EPOCHS=3]
	cd backend && ../$(VENV)/python scripts/train_distilbert.py "$(DATASET)" --epochs $(or $(EPOCHS),3)

generate:  ## pre-generate drafts for pending messages so opening them is instant (needs make agent)
	cd backend && ../$(VENV)/python scripts/generate_pending.py
