# Writing profile: drafts that sound like the user, learned in the open

- **Status:** draft (phase 0 is the experiment; phases 1 and 2 depend on its result)
- **Owner:** veyroxie (Lane B storage and extraction, Lane C prompt, Lane D settings card)
- **Related issue:** product brainstorm 2026-09-30 ("understood"); feeds
  [`model-feedback-routing.md`](./model-feedback-routing.md)
- **Last updated:** 2026-09-30

## Goal

Each edit the user makes to a draft teaches AImail how they write, so later drafts need fewer
edits. The user can see everything learned, correct it and delete it. It belongs to them alone:
AImail remembers them, and the model provider does not.

## User story

As an employee, I want AImail's drafts to open, close and phrase things the way I do, and I want
to see what it has learned about me, so that I trust the drafts and do not feel watched.

## Scope

**In scope**
- **Phase 0, capture (the experiment):** at send, keep the draft as it was shown alongside what
  was sent, plus an edit ratio. No learning and no UI. Run for two weeks of real use.
- **Phase 1, learn:** a deterministic extractor turns the draft/sent pairs into profile entries:
  greeting, sign-off, typical length, formality, language, and repeated phrase swaps ("Please
  advise" becoming "Let me know").
- **Phase 2, show and use:** a "How you write" card in Settings, and a short style hint appended
  to the existing drafting profile (`Policy.profile_text`).

**Out of scope**
- Fine-tuning or training any model on the user's email. The profile is a set of readable entries,
  not weights.
- Learning across users, or a team voice for shared inboxes.
- Any admin view of a profile.

## Acceptance criteria

- [ ] **Phase 0.** Given a draft shown to the user, when they send an edited version, then the
      shown draft, the sent text and the edit ratio (normalised Levenshtein) are all stored, and
      `draft_reply` still holds the sent text as it does today.
- [ ] **Phase 0 exit.** After two weeks, a report lists how many sends were captured and which
      features were consistent (same value in at least 70% of sends). Phase 1 starts only if at
      least three features are consistent; otherwise this spec is revised.
- [ ] **Phase 1.** Given a feature observed fewer than `MIN_EVIDENCE` (3) times, then no profile
      entry exists for it. One reply to one colleague does not become a habit.
- [ ] **Phase 1.** Given a candidate phrase swap containing a digit, `@`, a URL, or a capitalised
      word not at sentence start, then it is dropped and never stored.
- [ ] **Phase 2.** Given a learned entry, then the card shows the entry and its evidence ("in 7 of
      your last 10 replies"), with edit and delete controls.
- [ ] **Phase 2.** Given the user deletes an entry, then it never returns. Given they pause
      learning, then no new entries are created. Given "delete everything", then the profile and
      every stored draft/sent pair are removed.
- [ ] **Phase 2.** No admin route returns profile entries or draft/sent pairs (asserted by a test
      over the admin app's route table).
- [ ] **Phase 2.** Given a profile, then the drafting request carries at most `STYLE_HINT_CHARS`
      of style hint, fenced as data like the rest of the prompt, and no raw sent text.
- [ ] **Outcome.** The median edit ratio over the most recent 30 sends is lower than over the
      first 30 after phase 2 ships. This is the chart `model-feedback-routing.md` asks for.

## API surface

To be added to `specs/context/api-contracts.md` in phase 2:

- `GET /profile/writing`: entries with evidence counts, and whether learning is paused.
- `PATCH /profile/writing/{entry_id}`: edit the value.
- `DELETE /profile/writing/{entry_id}`: delete one entry and suppress it permanently.
- `PUT /profile/writing/learning`: pause or resume.
- `DELETE /profile/writing`: delete everything, including the draft/sent pairs.

## Data model

- **Phase 0, `messages.draft_shown`** (`TEXT NULL`): the draft as it stood when the user pressed
  send. `approve_and_send` copies `draft_reply` here before overwriting it with the sent text
  (today the generated version is lost). Plus `messages.edit_ratio` (`REAL NULL`).
- **Phase 1, `style_entry`** (the `style_profile` placeholder in `db-schema.md`): `id`, `user_id`,
  `kind` (`greeting|signoff|length|formality|language|phrase_swap`, CHECK-constrained), `value`
  (JSONB), `scope` (`all` or a correspondent's domain), `evidence`, `source` (`learned|user`),
  `suppressed` (`BOOLEAN`), timestamps.

## Dependencies

- `approve_and_send` in `backend/app/dashboard.py` (the capture point).
- `app/personalisation.py` (`Policy.profile_text`, already the one prompt channel for the user profile).
- No new third-party dependency: the edit ratio and feature extraction are standard-library code.

## Edge cases & failure modes

- **Sent unedited:** still recorded (ratio 0). An accepted draft is evidence too.
- **Rewritten from scratch:** a ratio near 1 says the draft missed, not how the user writes a
  greeting. Pairs above `REWRITE_RATIO` (0.8) feed only length and language features, not
  phrase swaps.
- **Mixed-language replies:** language is recorded per reply, and scoped by correspondent's domain
  once there is enough evidence.
- **Contradictory habits:** a formal greeting for one domain and a casual one for another become
  two scoped entries, not a flip-flopping global one.

## Security & privacy notes

- **Sent text is unmasked:** the user typed real names into it. It is stored in Postgres (as
  `draft_reply` already is after a send) and never leaves the machine raw. Only extracted entries
  that pass the PII screen can reach the model.
- **Employer visibility:** the profile is the employee's data about how they write. The admin
  console never reads it. Under the PDPA the employee can see and correct their own data, and the
  settings card is where they do that.
- **Delete everything means everything:** entries, suppressed markers and draft/sent pairs.

## Open questions

- Is the PII screen in phase 1 strict enough? It is deliberately crude (it drops anything with a
  digit, `@`, URL or mid-sentence capital). The phase 0 data will show how many useful phrases it
  loses.
- Should the style hint also be scoped per correspondent when drafting? It needs `from_addr`
  (unmasked) to pick the scope. The lookup is local, and only the resulting hint is sent, so the
  address still never enters the payload.

## Out-of-scope future extensions

- A local fine-tuned model for style (see the conversation of 2026-09-30). Only worth trying if
  the phase 2 outcome criterion fails with a good profile.
- Suggesting new holding-reply templates in the user's own voice.

## Protected decisions

<!-- BEGIN PROTECTED -->
The writing profile is visible only to the user it describes. No admin route, report or export
reads it. Rationale: "understood" turns into "monitored" the moment an employer can read how an
employee writes. DO NOT change this without the mailbox owner's approval recorded in
docs/decisions/shared.md.
<!-- END PROTECTED -->
