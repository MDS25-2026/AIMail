# Local model: drafting on the user's own GPU, with masking unchanged

- **Status:** idea (the baseline experiment decides whether it becomes a draft)
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

## Scope

**In scope (experiment, outside the repo, in `~/llm-lab`)**
- **Baseline:** 5 to 10 already-masked emails, one prompt, drafted by the local model and by
  Gemini, scored side by side (send as is / small edits / unusable).
- **Fine-tune trial:** a QLoRA adapter on a 1B model from masked draft/sent pairs (see
  [`writing-profile.md`](./writing-profile.md), phase 0, for where the pairs come from).

**In scope (only if the baseline passes)**
- A provider setting for Lane C: `gemini` (default) or `local`, with the Ollama address in `.env`
  (`LOCAL_LLM_URL`, default `http://localhost:11434`) and in `.env.example`.
- Drafting through the existing pre-generation poller, so per-draft latency is invisible to the user.

**Out of scope**
- Dropping masking for the local path (see Protected decisions).
- Serving the model to other machines over the network.
- Summaries, translation and the critic on the local model: drafting first, the rest only if it works.

## Acceptance criteria

- [ ] **Experiment gate.** On the same masked emails, the local model's drafts score "send as is"
      or "small edits" at least as often as Gemini's minus one. Below that, this spec is archived
      with the results recorded here.
- [ ] Given `LLM_PROVIDER=local`, when a draft is generated, then no request reaches any Gemini
      endpoint (asserted by a test that fails on any outbound call to the Gemini base URL).
- [ ] Given `LLM_PROVIDER=local` and Ollama is not running, then generation fails with the same
      typed `UNAVAILABLE` code the Gemini client uses, and the draft is retried later; it never
      falls back to Gemini silently.
- [ ] Given the local provider, then every draft still passes the existing critic gates (PII,
      grounding, markers unchanged) before it is shown.
- [ ] The prompt a local draft is generated from contains only masked text, identical to what the
      Gemini path sends.

## Edge cases & failure modes

- **Out of GPU memory** (a game or another model loaded): Ollama spills to the CPU and slows down
  sharply. The poller's per-attempt timeout must allow for that, then count it as a failed attempt.
- **Several emails arrive at once:** on 4 GB, one generation at a time (`OLLAMA_NUM_PARALLEL=1`).
  Ten emails queue for about two minutes in the background, which is acceptable.
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
