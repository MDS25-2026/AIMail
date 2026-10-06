# Normalisation layer: numbers, units and dates in one place

- **Status:** shipped
- **Owner:** veyroxie
- **Related issue:** hackathon-reuse review (normalisation), user request 2026-09-29
- **Last updated:** 2026-09-29

## Goal

One module turns the ways people write numbers, quantities and dates into one comparable form,
so the dashboard can show a quantity in the reader's unit system and every check that compares
figures (the draft's unsupported-specifics gate, translation) compares values, not spellings.

## Scope

**In scope** (`backend/app/normalise/`)
- `numbers`: `18,400.00`, European `21.577,00`, `21 577,5` and `1.234.567` all parse to one float
  (ported from the hackathon's tested `parse_number`).
- `quantities`: a number followed by a unit from a closed vocabulary (mass, length, volume,
  temperature, area, speed), converted with `pint` to both metric and imperial, rounded to three
  significant figures for display.
- `dates`: every date format `app/ml/temporal.py` read, moved here; slash dates read day-first
  unless one side is over 12, with the ambiguous case set by `DATE_ORDER` (`DMY` default).
- The unsupported-specifics gate accepts a draft figure that is a correct unit conversion of a
  source figure (within 1%), and still flags a wrong one.
- `DashboardEmail.quantities`: every quantity in the masked body, with both systems.

**Out of scope**
- Currency conversion. Exchange rates need a live external feed, and a converted amount in a
  reply is a financial statement the source never made. Amounts are compared as numbers only.
- Ambiguous words: "pound" (weight or money), bare "in", "t", "MT": never read as units.

## Acceptance criteria (`tests/test_normalise.py`)

- [x] `21.577,00`, `21 577,5`, `40,326` and `18,400.00` parse to 21577.0, 21577.5, 40326, 18400.
- [x] "2,000 lb" gives 907 kg; "30 °C" gives 86 °F; "5 km" gives 3.11 mi.
- [x] "5G network", "in 2 days" and "50 pounds" are not quantities.
- [x] "30/09/2026" is 30 September; "8/15/2026" is 15 August; "05/09/2026" follows DATE_ORDER.
- [x] A draft saying "4,409 lb" against a source saying "2,000 kg" is supported; "4,000 lb" is not.

## Security & privacy notes

Runs locally on already-masked text; no content leaves the process. Masking replaces names and
contact details, never figures, so quantities survive it intact.
