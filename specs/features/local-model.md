# Local model: drafting on the user's own GPU, with masking unchanged

- **Status:** Private mode built 2026-10-06 (Gemma 4 E2B; blind human rating running)
- **Owner:** veyroxie (experiment); Lane C (Hanif) for any change to `email_agent.py` / `gemini_client.py`
- **Related issue:** conversation of 2026-09-30; guide `local-llm-guide.pdf` (kept outside the repo)
- **Last updated:** 2026-09-30

## Goal

Draft replies with an open model served by Ollama on the user's own machine, so that no email
text, masked or not, reaches a model provider, while every other privacy guarantee stays as it is.

## What we know so far (measured 2026-09-30)

- Hardware: RTX 3050 Laptop GPU, 4 GB VRAM, WSL2. Ollama 0.35.0 (official installer; the snap
  build ran on the CPU only).
- `qwen2.5:3b` (4-bit, 1.9 GB) runs 100% on the GPU using 2.2 GB of VRAM: about 19 to 22
  tokens/s, so about 10 s for a 150-word reply.
- Quality: small errors already visible in simple prompts (wrong pinyin, one line when two were
  asked for). A 3B model is not expected to match Gemini, especially in Malay and Chinese.

## Baseline result (2026-10-06)

Nine made-up emails (3 English, 3 Malay, 3 Chinese, in placeholder form, four with a policy
snippet), the production drafting prompt for every model, Gemini's critic scoring every draft.
Harness and data in `~/llm-lab` (`benchmark.json`, `compare.py`, `summary.py`).

| Model | Median time | Right language | Placeholders kept | Critic: tone | Critic: complete | Critic confidence (median) |
|---|---|---|---|---|---|---|
| Gemini 2.5 Flash | 1.3 s | 9/9 | 8/9 | 9/9 | 9/9 | 0.95 |
| **Gemma 4 E2B** | 6.2 s | 6/9, **9/9 with a language rule** | 9/9 | 8/9 | 8/9 | 0.95 |
| Qwen2.5 3B | 5.3 s | 9/9 | 9/9 | 6/9 | 6/9 | 0.5 |
| Qwen3 4B (instruct) | 9.5 s | 9/9 | 9/9 | 4/9 | 3/9 | 0.2 |

- **Gemma 4 E2B is the local candidate.** It answered three Malay/Chinese emails in English until
  the prompt said "Write the reply in the same language as the email_body"; with that line all
  five rechecked emails came back in the right language.
- Gemma 4 E2B is 4.6 GB, more than the 4 GB card, so part of it runs on the CPU; still about 6 s.
- `qwen3:4b` is the thinking edition and writes its reasoning into the reply; only the
  `-instruct` edition is usable for drafting.
- **Not yet done:** the human rating the experiment gate asks for (send as is / small edits /
  unusable). The critic is a proxy, and Gemini judging Gemini is biased in Gemini's favour.

## Human rating, pilot (2026-10-07)

Blind page (`~/llm-lab/rating-template.html`, model key kept off the page in `rating-key.json`),
each rater choosing the languages they read. One rater so far, 21 drafts (English, Malay, one Chinese):

| Model | Send as is | Small edits | Unusable | Usable |
|---|---|---|---|---|
| Gemini 2.5 Flash | 4 | 3 | 0 | 7/7 |
| Gemma 4 E2B | 1 | 5 | 1 | 6/7 |
| Qwen2.5 3B | 4 | 1 | 2 | 5/7 |

- Gemma meets the gate (usable at least Gemini's count minus one), on one rater only; more ratings,
  above all in Chinese and Malay, are needed before it is more than a pilot.
- The rater's edits to Gemma were about politeness, not correctness. The writing style covers that
  without training: one line ("Always thank the sender first") changed Gemma's draft to open with
  thanks. Quick picks in the card make it one tap (`writing-profile.md`).

## Per-user training (roadmap, after user testing)

Owner, 2026-10-07: "i do wanna use gemma, and it shld be like trainable per user but shdl also
scale well"; the proof of concept waits for the testing data.

1. **Now:** the writing style (description, quick picks, examples, learned habits) is the per-user
   layer. It costs nothing per user and works the same with Gemma and Gemini.
2. **During user testing:** testers switch on "Learn from the replies I send", which stores masked
   draft/sent pairs (`writing-profile.md`). That is the training data.
3. **After testing:** a LoRA adapter per user on the shared Gemma base (QLoRA, e.g. Unsloth), from
   that user's pairs, once they have a few hundred. Served by a multi-adapter server (vLLM or
   llama.cpp server), which keeps one base model in memory and applies each user's adapter per
   request: hundreds of users per GPU. Ollama loads one adapter at a time, so it stays for the
   demo only. Deleting a user's adapter file forgets them.

## Scope

**In scope (experiment, outside the repo, in `~/llm-lab`)**
- **Baseline:** 5 to 10 already-masked emails, one prompt, drafted by the local model and by
  Gemini, scored side by side (send as is / small edits / unusable).
- **Fine-tune trial:** a QLoRA adapter on a 1B model from masked draft/sent pairs (see
  [`writing-profile.md`](./writing-profile.md), phase 0, for where the pairs come from).

**In scope: Private mode (built 2026-10-06, after the baseline; the human rating is running)**
- **Company gate:** `LOCAL_LLM_URL` (default `http://localhost:11434`) and `LOCAL_LLM_MODEL` (e.g.
  `gemma4:e2b`) in `.env`. With no model set, Private mode is not offered and the backend refuses it.
- **Per-user choice:** Settings > Private mode, stored as `user_preferences.draft_provider`
  (`gemini` or `local`, migration 0022).
- **Every agent model call** for that user's emails goes to the local model: router, summary, action
  items, draft, critic, refine rounds, the user's own refine, and translation. One switch point:
  `email_agent.call_gemini`, routed by the request's `provider` field.
- **Local search in Private mode (2026-10-07):** documents, and past replies (see
  [`writing-profile.md`](./writing-profile.md)), are searched with a local embedding model,
  `LOCAL_EMBEDDING_MODEL` (e.g. `embeddinggemma`, 768 dimensions, 2048-token input) on the same
  Ollama. Its vectors live in their own table, `local_embedding` (migration 0023), with their own
  index: a Gemini vector and a local one are not comparable and are never searched together.
  With no local embedding model set, Private mode drafts without search, as before, and the
  draft carries the "not grounded" review reason.
- **No Gemini embedding for a Private-mode user:** while a user is in Private mode, their chunks
  are embedded only locally. Every chunk gets a local vector (it never leaves the machine), so
  switching Private mode on finds documents at once. A background pass every `EMBED_POLL_SECONDS`
  (60 s) fills in whichever side is missing, so switching back to Gemini catches up on its own. Documents
  embedded with Gemini before the user switched were already sent to Google; switching does not
  undo that.
- Drafting still runs through the pre-generation poller (one email at a time), so the local
  model's 8 to 30 s per draft is mostly invisible.

**Out of scope**
- Dropping masking for the local path (see Protected decisions).
- Full-text search instead of a local embedding model: it matches words, not meaning, and cannot
  split Chinese words.
- `/ask`, which still answers with Gemini and searches Gemini vectors; the card says so. A
  Private-mode user's documents uploaded after switching have no Gemini vector, so `/ask` does not
  find them.
- Serving the model to other machines over the network.

## Acceptance criteria

- [ ] **Experiment gate.** On the same masked emails, the local model's drafts score "send as is"
      or "small edits" at least as often as Gemini's minus one (blind human rating). Below that,
      Private mode stays labelled "beta" and this section records the result.
- [x] Baseline (critic as a proxy): see "Baseline result" above.
- [ ] Given Private mode, when a draft, a refine or a translation is made, then no request reaches
      the Gemini generation endpoint or the embedding call (asserted by a test that fails on either).
- [ ] Given Private mode and Ollama is not running, then the request fails with the typed
      `UNAVAILABLE` code and the background drafter retries (up to 5 times); it never falls back
      to Gemini.
- [ ] Given Private mode is not configured, then the card does not offer switching it on and
      `PUT /settings/private-mode` refuses `enabled: true` with `409 private_mode_unavailable`.
      A user who already has it on still sees the card, with a warning and the off switch.
- [ ] Given drafting gave up on some emails (5 failed attempts, e.g. Ollama was down), when the
      user switches Private mode on or off, then those emails are drafted again. While it stays on,
      Regenerate retries one email.
- [ ] Given the local provider, then every draft still passes the fixed-rule gates (Presidio's PII
      scan, unsupported figures, markers). The critic is the local model, so it is a weaker gate.
- [ ] The prompt a local draft is generated from contains only masked text, identical to what the
      Gemini path sends.
- [ ] Given Private mode and a local embedding model, when a draft is made, then the search uses
      only `local_embedding`, and the Gemini embedding call is never made for that user's chunks,
      at upload, at send, or in the background pass (asserted by a test that fails if it is).
- [ ] Given two embedding passes at once, then no chunk gets two vectors from the same model.

## Edge cases & failure modes

- **Out of GPU memory** (a game or another model loaded): Ollama spills to the CPU and slows down
  sharply. The poller's per-attempt timeout must allow for that, then count it as a failed attempt.
- **Several emails arrive at once:** on 4 GB, one generation at a time (`OLLAMA_NUM_PARALLEL=1`).
  Ten emails queue for about two minutes in the background, which is acceptable.
- **Two models on 4 GB:** measured 2026-10-07, EmbeddingGemma and Gemma 4 E2B stay loaded
  together (3.4 of 4 GB). Warm, a search embeds in 0.1 s and a short Gemma call takes about 1 s;
  the first call after both were unloaded took 65 s.
- **Model unloaded after idling:** the first draft after a pause pays a few seconds of load time.
  `OLLAMA_KEEP_ALIVE` trades that against holding the VRAM permanently.

## Security & privacy notes

- A local model removes the provider from the path. It does **not** remove the need for masking:
  masking happens at ingest, before anything is stored in Supabase, which is hosted. Stored drafts
  also live there.
- Ollama must listen on `localhost` only. It has no authentication.
- Fine-tuning data and adapters are trained on masked text only, and are treated as sensitive:
  models memorise training data. They live in `~/llm-lab`, outside git and cloud sync.

## Open questions

- **Placeholder fill-in at the last step.** Drafts on masked text say `[PERSON_1]`. Filling real
  values back in only in the dashboard, never stored, would improve drafts for both providers. It
  needs the token-to-value mapping, which the masking design and
  [`translation.md`](./translation.md) currently rule out. It needs an ADR, not a setting.
- Which model? Qwen 2.5 3B is the measured candidate. Southeast Asian models (SEA-LION, MaLLaM)
  should join the baseline if a build fits in 4 GB.
- Does Ollama keep prompts in its logs? Check `journalctl -u ollama` before using real masked emails.

## Protected decisions

<!-- BEGIN PROTECTED -->
Masking stays at ingest regardless of where the model runs. A local model is never a reason to
store, send or train on unmasked email. Rationale: masking protects the hosted database and the
stored drafts, not only the model call, and "local" becomes a company server in any real
deployment. DO NOT change this without an ADR approved by the mailbox owner.
<!-- END PROTECTED -->
