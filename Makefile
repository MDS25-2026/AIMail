# AImail task runner. Deterministic commands only.
# Judgment/generation tasks live as Claude skills in .claude/skills/ instead.

VENV := .venv/bin
.DEFAULT_GOAL := help

.PHONY: help api-types api-types-check check test lint typecheck hooks dev backend worker agent web test-reader migrate seed ingest eval eval-reform baseline backfill generate ml-deps distilbert eval-classifier label eval-critic latency extension

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-12s %s\n", $$1, $$2}'

check: test lint typecheck api-types-check  ## backend tests + ruff; dashboard typecheck, eslint, unit tests, palette check; API types fresh

DASHBOARD := frontend/frontend/mail-clarity-dash-main
OPENAPI := backend/.openapi.json

api-types:  ## regenerate the dashboard's API types from the backend's OpenAPI schema
	cd backend && ../$(VENV)/python scripts/dump_openapi.py .openapi.json
	cd $(DASHBOARD) && npx openapi-typescript ../../../$(OPENAPI) -o src/lib/api/schema.gen.ts

api-types-check:  ## fail when the dashboard's API types no longer match the backend
	cd backend && ../$(VENV)/python scripts/dump_openapi.py .openapi.json
	cd $(DASHBOARD) && npx openapi-typescript ../../../$(OPENAPI) -o ../../../backend/.schema.check.ts
	diff -q backend/.schema.check.ts $(DASHBOARD)/src/lib/api/schema.gen.ts || (echo "API types are stale: run make api-types" && exit 1)

hooks:  ## install git hooks (pre-push runs 'make check')
	git config core.hooksPath .githooks
	@echo "hooks installed — pre-push now runs 'make check' (skip with: git push --no-verify)"

test:  ## backend unit tests
	cd backend && ../$(VENV)/pytest -q

lint:  ## backend lint
	cd backend && ../$(VENV)/ruff check app tests scripts *.py

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

worker:  ## run every background job (drafting, embedding, holding replies, retention, reconciliation)
	cd backend && ../$(VENV)/python -m app.worker

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

migrate:  ## apply every pending migration in order (schema_migrations records what ran)
	cd backend && ../$(VENV)/python scripts/migrate.py

seed:  ## load sample policy chunks
	cd backend && ../$(VENV)/python scripts/seed_demo.py

ingest:  ## ingest a policy PDF: make ingest PDF=path.pdf TITLE="Name"
	cd backend && ../$(VENV)/python scripts/ingest.py "$(PDF)" "$(TITLE)"

SET ?= eval/retrieval/v0.json
eval:  ## retrieval eval at today's cutoff: make eval [SET=eval/retrieval/v1.json OWNER=<uuid> PROVIDER=local]
	cd backend && ../$(VENV)/python scripts/eval_retrieval.py --set $(SET) $(if $(OWNER),--owner $(OWNER)) $(if $(PROVIDER),--provider $(PROVIDER))

eval-reform:  ## retrieval eval with query reformulation (S5), same options as eval
	cd backend && ../$(VENV)/python scripts/eval_retrieval.py --set $(SET) $(if $(OWNER),--owner $(OWNER)) $(if $(PROVIDER),--provider $(PROVIDER)) --reformulate

calibrate:  ## re-measure the retrieval cutoff and record it, same options as eval
	cd backend && ../$(VENV)/python scripts/eval_retrieval.py --set $(SET) $(if $(OWNER),--owner $(OWNER)) $(if $(PROVIDER),--provider $(PROVIDER)) --calibrate

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
