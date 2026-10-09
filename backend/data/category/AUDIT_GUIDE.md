# B2B Email Taxonomy Blind Audit Guide

This guide establishes the blind human evaluation protocol for our 6-category B2B email classifier (FIT3164 FYP Award — Section 05 "Triage & ML Efficiency").

---

## 1. Allowed Categories (Case-insensitive)

Please enter one of the exact 6 category tokens below in your reviewer column:

| Token | Display Category | Scope & Typical Triggers |
| :--- | :--- | :--- |
| `client` | Client / Customer | Deals, prospective enterprise pilots, customer onboarding, SLA credits, client support escalations, sales proposals |
| `vendor` | Vendor / Partner | Invoices, SaaS tool renewals, procurement, subcontractor Statements of Work (SOW), partner integrations, rate cards |
| `internal` | Internal / Team | Sprint standups, code reviews, PR migrations, team retrospective, blockers, 1-on-1 rescheduling, internal roadmap |
| `security` | Security / Compliance | SOC 2 Type II audit requests, compliance training deadlines, vulnerability notices, NDAs, access control reviews, DPA/GDPR |
| `admin` | Admin / Logistics | Facilities maintenance, town halls, room/AV bookings, corporate travel bookings, equipment return, holiday schedules |
| `personal` | Personal / Social | Informal coffee/lunch chats, birthday kudoboards, work anniversaries, weekend social events, casual banter |

---

## 2. Reviewer Instructions

File to edit: `backend/data/category/holdout_audit.csv`

1. **Shared Calibration Rows (Rows 1 to 12 — `assigned_reviewer = 'ALL'`)**:
   - **Han**: Fill in column `han_label`.
   - **JJ**: Fill in column `jj_label`.
   - **Hanif**: Fill in column `hanif_label`.
   - *Purpose*: These 12 shared rows are evaluated by all three auditors independently to calculate **Cohen's / Fleiss' Kappa ($\kappa$)** (inter-annotator agreement) for our poster.

2. **Individually Assigned Rows (Rows 13 to 120)**:
   - When `assigned_reviewer == 'Han'`: Han fills in `han_label`.
   - When `assigned_reviewer == 'JJ'`: JJ fills in `jj_label`.
   - When `assigned_reviewer == 'Hanif'`: Hanif fills in `hanif_label`.

3. **Notes Column (Optional)**:
   - If an email is ambiguous, mention why in `notes` (e.g. *"overlaps vendor billing and client support"*).

---

## 3. Automated Reconciliation

Once all three auditors finish and commit their columns, run:
```bash
python scripts/reconcile_category_audit.py
```
This script will automatically:
1. Compute pairwise Cohen's Kappa ($\kappa$) on the 12 shared rows.
2. Build the verified gold test set `holdout_gold.csv`.
3. Re-run `eval_category_classifier.py` and output the audited poster metrics.
