# Category classifier (6-category B2B email taxonomy)

- **Status:** in-progress
- **Owner:** @HanifRafli (with @05jiujing, @HyperByte12263)
- **Related issue:** #141
- **Last updated:** 2026-10-08

## Goal

Provide every incoming email with a functional business category from Han's 6-category B2B knowledge-worker taxonomy (`Client / Customer`, `Vendor / Partner`, `Internal / Team`, `Security / Compliance`, `Admin / Logistics`, `Personal / Social`), giving the team a dedicated, lightweight machine learning deliverable evaluated on an independent human-verified gold test set.

This classifier fulfills the quantitative deliverable for **Empirical Pillar 1 ("Triage & ML Efficiency")** in **Poster Section 05** for the Monash SoIT FYP Award competition, delivering **<50ms CPU inference latency** and **>=85% Macro-F1**.

Category is **orthogonal to Urgency / Priority**:
- **Category** (Issue #141, ML classifier) — "What functional domain does this email belong to?"
- **Temporal Urgency & Priority** (Issue #142, deterministic regex SLA floor) — "How urgently does the recipient need to act?"

## User story

As a corporate knowledge worker and inbox operator, I want incoming emails automatically classified into functional business categories (e.g., client requests, vendor invoices, security reviews), so that the dashboard inbox can be organized and filtered by operational context without waiting for slow cloud LLM API calls.

## Scope

**In scope**
- Supervised 6-class B2B taxonomy:
  1. `Client / Customer` (`client`)
  2. `Vendor / Partner` (`vendor`)
  3. `Internal / Team` (`internal`)
  4. `Security / Compliance` (`security`)
  5. `Admin / Logistics` (`admin`)
  6. `Personal / Social` (`personal`)
- Tri-source dataset bootstrapping:
  - LLM-assisted synthetic generation via Gemini Flash for modern B2B domains (`Client`, `Vendor`, `Security`).
  - Corporate email fixtures and sanitized Enron samples (`Internal`, `Admin`, `Personal`).
  - Human-audited 120-row gold holdout evaluation set (20 per category, audited by Hanif, JJ, and Han).
- Feature extraction and model training:
  - TF-IDF vectorization (unigrams + bigrams, sublinear term frequency).
  - Calibrated Linear / Logistic Regression classification.
  - Evaluation reporting: Stratified split, per-class Precision/Recall/F1, Macro-F1, and Confusion Matrix.
- 300 DPI annotated Confusion Matrix heatmap export (`results/category_confusion_matrix.png`) for Poster Section 05.
- Inference runtime surface: `predict_category(masked_email_text: str) -> tuple[EmailCategory, float]`.
- Database persistence: `category` and `category_confidence` columns on `messages` table via migration `0033_email_category.sql`.
- REST API and dashboard contract integration in `DashboardEmail`.

**Out of scope**
- Multi-label classification (each email is mapped to its primary functional category).
- Zero-shot LLM prompts during runtime inbox ingestion (explicitly rejected per Meeting 30 and Sergio's advice due to latency, API cost, and non-deterministic variability).
- Automated email dispatches triggered solely by category.
- Non-English email classification (evaluated on English corpora; foreign language text handled by Lane C translation layer).

## Acceptance criteria

- [ ] Given a training dataset of >=600 emails, when the training pipeline runs, it produces a stratified train/validation split and reports balanced per-class distributions.
- [ ] Given the held-out 120-row human gold test set, the trained classifier achieves **>=85.0% Macro-F1**.
- [ ] Given an email text payload, `predict_category` executes in **< 50ms** on CPU (target < 15ms) without initiating any external network or LLM API calls.
- [ ] Given incoming text, `predict_category` operates **strictly on masked text** (`body_masked`, `snippet_masked`) containing PII tokens (`[PERSON_1]`, `[ORG_1]`, etc.).
- [ ] Given an empty, whitespace-only, or unparseable email body, `predict_category` defaults gracefully to `internal` at low confidence without throwing an unhandled exception.
- [ ] Given database migration `0033_email_category.sql`, `messages` table persists `category` (`TEXT`) and `category_confidence` (`REAL`).
- [ ] Given `GET /emails` and `GET /emails/{id}`, the API response contract `DashboardEmail` includes `category` and `categoryConfidence`.
- [ ] Given the evaluation script `scripts/eval_category_classifier.py`, it exports `results/category_confusion_matrix.png` at 300 DPI suitable for print inclusion in Poster Section 05.

## API surface

### Internal Python Inference (`app/ml/category.py`)

```python
from enum import StrEnum

class EmailCategory(StrEnum):
    CLIENT = "client"        # Client / Customer
    VENDOR = "vendor"        # Vendor / Partner
    INTERNAL = "internal"    # Internal / Team
    SECURITY = "security"    # Security / Compliance
    ADMIN = "admin"          # Admin / Logistics
    PERSONAL = "personal"    # Personal / Social

def predict_category(text: str) -> tuple[EmailCategory, float]:
    """Predicts primary category and calibrated confidence (0.0 - 1.0) on masked text."""
    ...
```

### Shared Contract (`app/contracts.py` & `specs/context/api-contracts.md`)

```python
class DashboardEmail(BaseModel):
    id: str
    ...
    category: Literal["client", "vendor", "internal", "security", "admin", "personal"]
    categoryConfidence: float | None = None
```

## Data model

Database migration: `backend/app/db/migrations/0033_email_category.sql`:

```sql
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS category TEXT NULL,
ADD COLUMN IF NOT EXISTS category_confidence REAL NULL;

CREATE INDEX IF NOT EXISTS messages_category_idx ON messages(category);
```

- `messages.category` — `TEXT NULL`: The stable functional category predicted by the classifier.
- `messages.category_confidence` — `REAL NULL`: Calibrated probability score (0.0 to 1.0).

## Labelling & Taxonomy Rubric (6-Category B2B)

Emails are classified by their **functional business purpose**:

1. **`Client / Customer` (`client`)**:
   - Inbound queries from clients, prospects, or customer accounts.
   - Sales opportunities, product demo requests, quote inquiries, contracts under negotiation.
   - External customer support issues, onboarding requests.
2. **`Vendor / Partner` (`vendor`)**:
   - Inbound correspondence from software vendors, suppliers, consultants, or business partners.
   - SaaS license renewals, contract terms, procurement requests, API integration discussions.
   - Routine billing invoices and receipts from third-party services.
3. **`Internal / Team` (`internal`)**:
   - Routine peer-to-peer collaboration, 1-on-1s, engineering standups, sprint retrospectives.
   - Pull request reviews, technical design discussions, blocker alerts.
   - Department-level updates where the recipient is directly involved.
4. **`Security / Compliance` (`security`)**:
   - SOC 2, ISO 27001, GDPR, or PDPA audit questionnaires.
   - Vulnerability notifications, incident reports, penetration test findings.
   - Legal non-disclosure agreements (NDAs), terms of service updates, employee policy acknowledgments.
   - *Precedence Rule*: If an email involves an explicit security or compliance risk (even from a vendor or client), it defaults to `security`.
5. **`Admin / Logistics` (`admin`)**:
   - Company-wide all-hands announcements, holiday schedules, office facilities.
   - Meeting room reservations, travel bookings, flight confirmations.
   - Corporate catering, hardware provisioning requests.
6. **`Personal / Social` (`personal`)**:
   - Informal colleague chatter, coffee catchups, team lunch plans.
   - Birthday greetings, farewell notes, social watercooler banter.
   - Non-work personal communications.

## Dependencies

- `scikit-learn` (core ML pipeline — already in `.venv`).
- `joblib` (model serialization — already in `.venv`).
- `pandas` (dataset ingestion and splitting).
- `matplotlib` & `seaborn` (300 DPI confusion matrix plot generation — dependency addition).

## Edge cases & failure modes

- **Model artifact missing**: If `models/category-classifier.joblib` is not yet built, `predict_category` raises `ModelNotTrainedError` in development or falls back to `EmailCategory.INTERNAL` with confidence 0.0 in production resilience mode.
- **Short or stub emails**: Texts under 20 characters (e.g. "Thanks!", "Got it.") default to `EmailCategory.PERSONAL` or `INTERNAL` without crashing.
- **Unseen vocabulary / Out-of-Vocabulary (OOV)**: Handled robustly by sublinear TF-IDF character and word n-grams with laplace smoothing.
- **High PII token concentration**: Text consisting predominantly of `[PERSON_1]` and `[ORG_1]` retains syntax and context stopwords to identify domain intent.

## Security & privacy notes

<!-- BEGIN PROTECTED -->
Inference runs strictly on masked email text (`messages.body_masked` or `messages.snippet_masked`). 
Raw PII (names, phone numbers, IC numbers, bank accounts) MUST NEVER reach the classifier training scripts or inference runtime.
Classification outputs are purely informational signals for dashboard display and organization; they MUST NOT trigger automated email dispatch without human approval.
<!-- END PROTECTED -->

## Open questions

- **Tie-breaking confidence threshold**: If the top predicted class confidence is below 0.35, should the UI display a "Uncertain" indicator? (Resolution: display predicted class, but record `categoryConfidence` so the frontend can optionally style low-confidence badges subtly).

## Out-of-scope future extensions

- Hierarchical sub-categorization (e.g., `Client -> Support Ticket` vs `Client -> Enterprise Deal`).
- Per-user custom taxonomy rule overrides.
- Multi-language classification across Malay and Chinese without English translation.

## Implementation notes

- Script structure:
  - `backend/scripts/generate_category_dataset.py`: Synthetic generator and corpus compiler.
  - `backend/scripts/train_category_classifier.py`: Training, tuning, and artifact generation.
  - `backend/scripts/eval_category_classifier.py`: Evaluation on gold holdout set and 300 DPI plot export.
- Model artifact location: `backend/models/category-classifier.joblib`.
- Export results location: `backend/results/category_metrics.json` and `backend/results/category_confusion_matrix.png`.

## Decisions

- 2026-10-08: Selected TF-IDF + Logistic Regression/Calibrated LinearSVC as primary architecture. Rationale: <5ms CPU latency easily satisfies <50ms gate; zero network overhead; lightweight ~3 MB joblib artifact.
- 2026-10-08: Adopted tri-source hybrid dataset strategy (synthetic Gemini Flash generation + corporate fixtures + 120-row human-audited gold holdout). Rationale: overcomes lack of pre-existing labeled datasets for Han's custom taxonomy while preserving empirical validity for academic defense.
- 2026-10-08: Database migration `0033_email_category.sql`, renumbered from 0025 when #168 took 0025 to 0032 (migration numbers must be unique).

## Protected decisions

<!-- BEGIN PROTECTED -->
The category classifier is a trained supervised model evaluated against a human-verified gold holdout set, with an empirical confusion matrix and Macro-F1 metric reported.
Under no circumstances may inbox categorization be reverted to an external LLM zero-shot prompt during standard inbox triage.
<!-- END PROTECTED -->
