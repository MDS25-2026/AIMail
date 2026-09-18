# Known issues — found after the 2026-08-26 audit

Defects and limitations discovered while testing the system, not covered by the original audit's
nine items (those live in [`audit-remediation-plan.md`](audit-remediation-plan.md)). Recorded so
they are addressed deliberately rather than rediscovered.

Each entry: what happens, why it happens if known, and how much it matters.

## Open

### Page scrolls past the app into empty space — Lane D
The dashboard can be scrolled below the interface into blank space. An attempted fix (2026-09-04)
changed the shell from `h-screen` to `h-dvh` with `overflow-hidden` and set `html, body` to
`height: 100%` — **this did not resolve it**. Body overflow was deliberately not locked, since
`/extension` is a taller standalone page that must still scroll. Cosmetic, but visible in a demo.

**Measured 2026-09-15 (Lane B, handing to Lane D).** Three in-browser measurements:

| run | viewport | `html.scrollHeight` | verdict |
|-----|----------|---------------------|---------|
| 1   | 812      | 812                 | clean   |
| 2   | 812      | 3636                | **bug reproduced** |
| 3   | 731      | 731                 | clean   |

Run 3's viewport changed because devtools were docked, which forces a relayout. **The overflow is
transient: it survives until something invalidates layout, then clears.** That is why the container
fix looked like it failed and why the bug resists on-demand reproduction — measuring after a resize
destroys the evidence. In run 2 the document height (3636) tracked the inbox list's own content
height (3628, `InboxList.tsx:17`) to within 8px, but which element carries that height out to the
document root is **not** established.

Separately, and not the cause: `routes/index.tsx:117` (`aside`) and `:125` (`section`) sit between
`main.flex.min-h-0.flex-1` (`AppShell.tsx:20`) and both scroll containers, and carry neither
`h-full` nor `min-h-0`. They depend entirely on `align-items: stretch` for their height, which is
the fragile case when a child uses `h-full`. Worth tightening regardless.

Next step is to run this in the browser and then use the app normally — pop devtools into a
separate window first, because docking or resizing it clears the state being hunted. It stays quiet
until the overflow appears, then names the deepest element that no ancestor clips.

```js
(() => {
  const de = document.documentElement;
  let wasOverflowing = false;

  const clipper = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) {
      const o = getComputedStyle(n).overflowY;
      if (o === 'hidden' || o === 'auto' || o === 'scroll')
        return n.tagName + '.' + String(n.className || '').slice(0, 30);
    }
    return 'NONE';
  };

  window.__scrollWatch = setInterval(() => {
    const isOverflowing = de.scrollHeight > de.clientHeight + 4;
    if (isOverflowing === wasOverflowing) return;
    wasOverflowing = isOverflowing;
    if (!isOverflowing) return console.log('--- cleared');

    const shell = document.querySelector('.h-dvh');
    console.log('=== OVERFLOW', de.scrollHeight, 'vs', de.clientHeight,
      '| route', location.pathname,
      '| body children', document.body.children.length,
      '| h-dvh resolves to', shell ? getComputedStyle(shell).height : 'shell not found');

    [...document.querySelectorAll('*')]
      .map((el) => ({ el, bottom: Math.round(el.getBoundingClientRect().bottom + window.scrollY) }))
      .filter((o) => o.bottom > de.clientHeight + 4 && clipper(o.el) === 'NONE')
      .sort((a, b) => b.bottom - a.bottom)
      .slice(0, 8)
      .forEach(({ el, bottom }) => console.log('  ', bottom, el.tagName,
        String(el.className || '').slice(0, 45), '| pos', getComputedStyle(el).position));
  }, 250);

  console.log('watching. clearInterval(window.__scrollWatch) to stop.');
})()
```

### The Gmail watch is never renewed — Lane A
`setupWatch` registers a watch that Gmail expires after roughly seven days, and nothing renews it.
Restarting the listener re-registers, so frequent restarts hide the problem — but a listener left
running for a week would stop receiving mail silently. Needs a periodic re-registration.

### Pub/Sub messages are acknowledged before they are processed — Lane A
`msg.Ack()` is the first line of the receive callback, so a failure during masking or storage
means the notification is never redelivered and that email is lost. The alternative — acking after
success — risks a poison message redelivering forever. Neither is free; the current choice is
deliberate but undocumented outside this note.

### Ingestion fetches "the latest message" instead of what actually changed — Lane A
The Pub/Sub notification carries a history ID naming exactly what changed, and
`fetchLatestMessage` ignores it in favour of `Messages.List(...).MaxResults(1)`. If two emails
arrive close together, the second notification fetches the same newest message twice and the
earlier one is never ingested. The unique constraint on `gmail_message_id` prevents duplicate
rows, so the failure mode is a missed email rather than a corrupted one. Using the history
properly is the correct fix.

### Uploaded documents are never masked — Lane B
`ingest_text` chunks and embeds directly with no masking step, and those chunks become the RAG
context sent to the model. A policy PDF containing personal data reaches the LLM unmasked. The
mitigating argument is that uploaded documents are company policy chosen by the user rather than
third-party correspondence — but the privacy claim should be phrased as "no email body reaches
the model unmasked", not "nothing unmasked reaches the model".

### The refine instruction is unfenced user text — Lanes B/C
`/refine` interpolates a free-text instruction typed by the user straight into a prompt. It is the
one place a person can put arbitrary text in front of the model, and it should be fenced alongside
the untrusted-email fencing already planned for Lane C.

### The critic has never been validated against human judgement — Lane C
The confidence score is emitted by the model itself and is not compared to any human rating, so
"below 0.8 is flagged" rests on an unmeasured signal. A small study — two people rating ~20 drafts
good/bad, compared against the critic's pass/fail — would convert the project's weakest claim into
a measured one.

### `supabaseInsert` has no timeout — Lane A
It uses `http.DefaultClient` with no deadline, unlike the Presidio client which is bounded at five
seconds. A hung connection to Supabase would block that handler indefinitely.

### Generated drafts still contain a "Subject:" line — Lane C
The generator writes a subject line into the draft body. It is stripped at send time
(`gmail_send.py`), but it is still visible in the dashboard's draft editor and stored in
`draft_reply`. Better fixed in the generator prompt so the stored draft is clean.

### Training and evaluation data are not reproducible — Lane B
`.gitignore` excludes `backend/*.csv` and `backend/models/`, so no labelled dataset or trained
model is in version control. A clean clone cannot reproduce any reported number. Acceptable for
coursework; state it if asked about reproducibility.

## Known limitations, accepted deliberately

These are not defects — they are trade-offs with reasons, recorded so the reasoning is not lost.

- **Street numbers survive masking.** "12 Jalan Ampang" keeps the number. An address pattern would
  collide with dates, quantities and clause numbers, which the negative controls exist to prevent.
- **Organisation names are not masked.** Masking company names degrades draft quality, and the
  default NER model does not supply that entity type anyway.
- **A context-free account number is left visible.** The context gate is what stops every invoice
  and order number being redacted.
- **`from_addr` is stored unmasked.** `approve_and_send` needs a real recipient. It never enters
  the model payload.
- **Masking degrades rather than blocks.** If Presidio is unreachable, the regex floor still runs
  and the row is stored with the degradation recorded in the audit log. Names and locations are
  not masked in that mode.
- **A low-confidence draft is shown, not withheld.** Gating hard on an unvalidated self-reported
  score would silently discard work; the approval click is the real control.

## Housekeeping

- A stray `document` row titled "policy" with a single chunk is test residue in the RAG corpus.
- `models/distilbert-checkpoints/` is 1.4 GB of training artefacts; only `models/distilbert/` is
  used at runtime.
- Fourteen local branches exist, several from earlier team work that may never have merged.
