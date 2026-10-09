# Deterministic SLA Rules Floor

- **Status:** in-review
- **Owner:** @05jiujing (Lane A)
- **Related issues:** #142
- **Last updated:** 2026-10-08

## Goal

Provide a deterministic rule floor at the email ingestion layer (Lane A Go listener) that classifies incoming emails into SLA urgency tiers (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `""` unset) based on explicit deadlines and urgency cues, replacing blind AI defaults with guaranteed SLA handling.

## User story

As an email inbox operator, I want emails requesting urgent action within 24 hours to be tagged as `CRITICAL` and newsletters to be tagged as `LOW` deterministically at ingestion time, so that urgent customer or team demands are never missed even if downstream statistical models default to `MEDIUM`.

## Scope

**In scope**
- Ingestion-time rule classification in Go (`listener/sla.go`):
  - Rule 1: Newsletter / automated detection -> `LOW` (prevents marketing copy from false escalation).
  - Rule 2: Explicit urgency phrases and $\le 24$h deadlines -> `CRITICAL`.
  - Rule 3: Deadlines $\le 3$ days or tomorrow markers -> `HIGH`.
  - Rule 4: Deadlines $\le 7$ days or week markers -> `MEDIUM`.
  - Unset: Passthrough `""` (SLAUnset) allowing downstream AI / ML models to triage ambiguous emails.
- Multilingual urgency keyword support (English, Malay, Chinese).
- Calendar date parser supporting ISO (`YYYY-MM-DD`), slash (`DD/MM/YYYY`), and natural date strings (`March 15`, `15 March`).
- Database schema persistence via migration `0034_sla_priority.sql` with column `sla_priority` on `messages`.

**Out of scope**
- Natural language sentiment scoring (handled by Lane B classifier / temporal scorer).
- Direct email dispatch without human operator approval.
