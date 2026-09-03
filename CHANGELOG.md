# Changelog

## [1.2.0](https://github.com/MDS25-2026/AIMail/compare/v1.1.0...v1.2.0) (2026-09-03)


### Features

* **backend,frontend:** audit trail, upload limits, live nav destinations ([35ee94c](https://github.com/MDS25-2026/AIMail/commit/35ee94c7371f180279460d0ce1f05162760fce91))
* **backend:** bearer-token auth on every route (audit OWASP API1) ([15d82f2](https://github.com/MDS25-2026/AIMail/commit/15d82f24ea6a4dd4561e1b766834f57d174a66f2))
* **backend:** rate limit the ingestion routes ([#50](https://github.com/MDS25-2026/AIMail/issues/50)) ([552bd20](https://github.com/MDS25-2026/AIMail/commit/552bd20370fec75c5bf207ce64c52ad4588a1a5f))
* **frontend:** knowledge, drafts, sent and settings pages on React Query ([#53](https://github.com/MDS25-2026/AIMail/issues/53)) ([a2e441e](https://github.com/MDS25-2026/AIMail/commit/a2e441ef4a24da5012b79e21356c5b54798dfd98))
* **frontend:** run the extension panel preview on real data ([#58](https://github.com/MDS25-2026/AIMail/issues/58)) ([2f41b9b](https://github.com/MDS25-2026/AIMail/commit/2f41b9b206a8483b9d89f7bc052e56f0679076b1))
* **listener,docs,frontend:** masking test suite, Seam-1 closure, demo prep ([6dfa14a](https://github.com/MDS25-2026/AIMail/commit/6dfa14af424a60b0f0b4f5807c377913bf58453e))
* **listener:** layer Presidio NER masking on the regex PII floor ([124b312](https://github.com/MDS25-2026/AIMail/commit/124b31276e1bf256e89e6c372ebe5c3078d8ece7))
* **listener:** R02 recall harness, plus two masking gaps it exposed ([7b23103](https://github.com/MDS25-2026/AIMail/commit/7b23103cb0e3bd43398bf5c6836bfbd290148492))
* **ml:** human-vs-Gemini label agreement analysis (Cohen's kappa) ([0111ce2](https://github.com/MDS25-2026/AIMail/commit/0111ce2ed7fb9a4527985ed056d7c65e17a00042))
* **ml:** interactive terminal labeler for the holdout (one keypress per email) ([f2bac6f](https://github.com/MDS25-2026/AIMail/commit/f2bac6fe5763b6af90ef0eab8335046e4dd3f0a8))
* **ml:** labeler can re-label an existing text CSV (skips slow zip re-parse) ([cb1675d](https://github.com/MDS25-2026/AIMail/commit/cb1675d04e0320bbb76541e889bb43e59e78ae91))
* **ml:** PRIORITY_MODEL flag + eval-on-holdout command ([facf444](https://github.com/MDS25-2026/AIMail/commit/facf444163b1a464efed69fbbd9d38583b7453da))
* **ml:** scaffold DistilBERT fine-tuning (the model that beats the TF-IDF baseline) ([e325f5c](https://github.com/MDS25-2026/AIMail/commit/e325f5cb0d122d89d1dfc26d1fc3425c4d61fe08))
* **ml:** text cleaning + RoBERTa base + Pro labeling (classifier refinement 1&2) ([a391c23](https://github.com/MDS25-2026/AIMail/commit/a391c23e067b169091f704312436e73034a20d60))
* **ml:** tune DistilBERT training — class-weighted loss, warmup, best-checkpoint ([91e7213](https://github.com/MDS25-2026/AIMail/commit/91e72131b73bf7f5f3e7edf2faaa50c8ec9ef19b))
* **ml:** urgency-marker lexicon in the temporal layer (explainable, negation-guarded) ([99ea4b3](https://github.com/MDS25-2026/AIMail/commit/99ea4b34fcdd57a29af456d2620852a76ff54525))


### Bug Fixes

* **frontend:** point Vite at the repo-root .env so the auth token loads ([f42fc55](https://github.com/MDS25-2026/AIMail/commit/f42fc555a6683a3a543fff5804779a1a0d081abf))
* **frontend:** resolve the typescript peer conflict blocking CI ([#51](https://github.com/MDS25-2026/AIMail/issues/51)) ([c58d3ef](https://github.com/MDS25-2026/AIMail/commit/c58d3eff19b2bb16a7b838e2793c278f959ce3c4))
* HTML replies, local timestamps, send-path guard, cached tokens ([#62](https://github.com/MDS25-2026/AIMail/issues/62)) ([ab383ef](https://github.com/MDS25-2026/AIMail/commit/ab383efc7d65abc34c779c5e435b0d8c762c3756))
* **listener:** add card detection, stop masking countries, catch employee numbers ([#60](https://github.com/MDS25-2026/AIMail/issues/60)) ([0ea1ff7](https://github.com/MDS25-2026/AIMail/commit/0ea1ff71285e22f43f492de0c0de9f5198cbf028))
* **listener:** strip HTML before masking, and close two PII leaks ([#57](https://github.com/MDS25-2026/AIMail/issues/57)) ([a51e573](https://github.com/MDS25-2026/AIMail/commit/a51e5737507df52f6acfc9e8dbcfac708ba47005))
* **listener:** type PII by structure -- IC/phone/email to ordered regex, account stays in Presidio ([7f6368e](https://github.com/MDS25-2026/AIMail/commit/7f6368e5f58b9da6311865f7a1e509829fc6dcb5))
* **ml:** align cleaning + labeling with whole-thread rubric ([d6ccfe4](https://github.com/MDS25-2026/AIMail/commit/d6ccfe4f349bf4653fdb8d14eb3542bb7c93eff4))
* **ml:** default labeling to gemini-3.5-flash (Pro is quota-locked on free tier) ([b5e7249](https://github.com/MDS25-2026/AIMail/commit/b5e724986eee861ea6afee0bff7ad134277896c7))
* **ml:** labeling resilient to timeouts (catch TransportError), smaller batches ([789b309](https://github.com/MDS25-2026/AIMail/commit/789b309888ec5a4427d6a3b49579d5bf434caa3f))
* **ml:** pad batches in DistilBERT training (DataCollatorWithPadding) ([7e77ddb](https://github.com/MDS25-2026/AIMail/commit/7e77ddb9903d2ee4dae8605288ea18aedad5544d))
* survive transient network failures instead of dying quietly ([#61](https://github.com/MDS25-2026/AIMail/issues/61)) ([0ab6622](https://github.com/MDS25-2026/AIMail/commit/0ab6622c0addae21d120d046170fb71b923d2150))


### Documentation

* **ai:** priority-classifier methodology (rubric, LLM-assisted labeling, baseline vs DistilBERT) ([92d61fc](https://github.com/MDS25-2026/AIMail/commit/92d61fcd560789e6a73a97c16dd02415003d49fd))
* **ai:** record human-elicited boundary rules for the labeling rubric ([163a6fc](https://github.com/MDS25-2026/AIMail/commit/163a6fc3c740fada87813d68722ed61d01615230))
* **ai:** record real results — baseline 0.50 vs DistilBERT 0.57 on human holdout ([945c847](https://github.com/MDS25-2026/AIMail/commit/945c8470fc64832ff9eee9367c1f486827e3ba2d))
* classifier refinement plan (data-grounded options, ROI-ordered, tracked) ([5bcde9a](https://github.com/MDS25-2026/AIMail/commit/5bcde9a1475e1a9938cf19eef4f2f8aad7ddd447))
* **env:** document PRIORITY_MODEL flag in .env.example ([0ee0aff](https://github.com/MDS25-2026/AIMail/commit/0ee0aff5efcbc3e13fc16a183d91995069913ae8))
* **rag:** expand the retrieval corpus with real codes of conduct ([#52](https://github.com/MDS25-2026/AIMail/issues/52)) ([40de8e1](https://github.com/MDS25-2026/AIMail/commit/40de8e1b6a705a240a6023c4a5d85c459b9aabb9))
* record breakthrough — rubric-consistent labels lift classifier 0.57 -&gt; 0.69 ([9de4389](https://github.com/MDS25-2026/AIMail/commit/9de43892ba3b9753d8634d71107722815f57de77))
* refinement experiment results — all models within noise, labels are the ceiling ([9b48371](https://github.com/MDS25-2026/AIMail/commit/9b4837131e83632cb3b04a347416dbfc060f4a08))
* rewrite CLAUDE.md to match the architecture that actually exists ([b6a259f](https://github.com/MDS25-2026/AIMail/commit/b6a259f473d65fc8fd0b83fd844ca342f1c7061d))

## [1.1.0](https://github.com/MDS25-2026/AIMail/compare/v1.0.0...v1.1.0) (2026-08-20)


### Features

* **Go backend:** added draft Go webhook. Fixes [#3](https://github.com/MDS25-2026/AIMail/issues/3) ([d51ea14](https://github.com/MDS25-2026/AIMail/commit/d51ea142942f47430b7eef704f811c9741fdc47b))
* **ml:** Gemini-assisted labeling script for the Enron importance dataset ([74186b1](https://github.com/MDS25-2026/AIMail/commit/74186b1ae4465a2c27a0b4eaf5de3fec1db9cd0f))
* **ml:** pull disjoint holdout sample for human labeling (honest test set) ([9fc2d14](https://github.com/MDS25-2026/AIMail/commit/9fc2d1487f0f752974afc0265de186d2cdaa9f16))
* **ml:** refine importance rubric (action/stakes/authority; automated+social=LOW; dates to temporal layer) ([a12def3](https://github.com/MDS25-2026/AIMail/commit/a12def3a054dc4ae112edcaa407eb067b778a26b))
* wire the full pipeline end to end (Lanes A-D on one shared account) ([#28](https://github.com/MDS25-2026/AIMail/issues/28)) ([614bae1](https://github.com/MDS25-2026/AIMail/commit/614bae1d7865a5a4b8dc2c701fc6b5fa66f3896a))


### Bug Fixes

* missed idea status ([0592021](https://github.com/MDS25-2026/AIMail/commit/05920214f7a52727325c041375ea9ca914c3b786))
* **ml:** make labeling resilient — save incrementally, skip dead batches, bigger batches ([d18af42](https://github.com/MDS25-2026/AIMail/commit/d18af4267787cdf0725438f5c2ac9ab2bedcb1ac))


### Documentation

* **git:** add stacked-branch workflow (keep working before merge, step by step) ([23fa82a](https://github.com/MDS25-2026/AIMail/commit/23fa82aeab113efa754e976e6232be3a32e64fd9))
* **repo:** post-scaffold tweaks (rebase rule, copyright notice) ([#22](https://github.com/MDS25-2026/AIMail/issues/22)) ([8826237](https://github.com/MDS25-2026/AIMail/commit/88262378c371971c377196e2096c15dcaeff69d2))

## 1.0.0 (2026-04-30)


### Documentation

* **adr:** add ADR system with first two decisions ([8a9a47b](https://github.com/MDS25-2026/AIMail/commit/8a9a47b352b156c4912d806a4314f3b8bc7428fe)), closes [#1](https://github.com/MDS25-2026/AIMail/issues/1)
* **repo:** codify three-tier boundaries and tighter commit conventions ([cca9135](https://github.com/MDS25-2026/AIMail/commit/cca913595310d9975a214c425fb2547d7942df0c)), closes [#1](https://github.com/MDS25-2026/AIMail/issues/1)
* **repo:** require rebase onto main before opening PRs ([48ef227](https://github.com/MDS25-2026/AIMail/commit/48ef2273b91fe5e47c8e292817a9afcf2cf39624)), closes [#1](https://github.com/MDS25-2026/AIMail/issues/1)
* **specs:** add agent pipeline design and feature idea sketches ([aa82c5f](https://github.com/MDS25-2026/AIMail/commit/aa82c5fd6ab8d66b3663cfb25bbed50b49acfa0f)), closes [#1](https://github.com/MDS25-2026/AIMail/issues/1)
* **specs:** expand spec system with living-spec rules and template improvements ([afb2cbf](https://github.com/MDS25-2026/AIMail/commit/afb2cbf2dc132e90c48be5d6077ce98884d39ef8)), closes [#1](https://github.com/MDS25-2026/AIMail/issues/1)

## Changelog

All notable changes to AImail are documented in this file.

This file is **auto-generated by [Release Please](https://github.com/googleapis/release-please)** from Conventional Commits. Do not edit it by hand — your edits will be overwritten the next time Release Please opens a PR.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and AImail adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the project is pre-1.0, breaking changes may land in patch releases.

See [`docs/release-process.md`](docs/release-process.md) for how releases are cut.
