# Automated mail is low priority

- **Status:** built 2026-10-13
- **Owner:** veyroxie
- **Related issue:** #224 (R), #147 (raised with the team)
- **Last updated:** 2026-10-13

## Goal

Newsletters and notifications showed as Medium, above person-written email the model had scored Low.
Medium was the placeholder for an email the priority model never scored, and nothing scores new mail
(the model runs only from `scripts/backfill_importance.py`, and the hosted app does not have it).

## Scope

- In `apply_policy` (the per-user policy layer), an email with `is_automated` is **low**, after the
  SLA rules' critical floor and the user's own sender and keyword rules, and before the SLA's other
  levels and the model's score. So a security alert the SLA rules call critical stays critical, and a
  user can still raise a sender they care about.
- The priority model is not deployed for automatic scoring: its recorded accuracy is 53% (macro-F1
  0.50, `backend/results/baseline-metrics.json`) on three levels. That stays the team's call (#142).

## Acceptance criteria

- [ ] Given an automated email with no rules, then its priority is low.
- [ ] Given an automated email the SLA rules mark critical, then it stays critical.
- [ ] Given an automated email from a sender the user ranks high, then it is high.
- [ ] Given a person-written email, then nothing changes.
