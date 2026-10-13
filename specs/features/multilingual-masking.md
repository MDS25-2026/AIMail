# Masking Malay and Chinese mail correctly

- **Status:** built 2026-10-13
- **Owner:** veyroxie
- **Related issue:** #224 (found by the owner on 13 Oct)
- **Last updated:** 2026-10-13

## Goal

The listener asks Presidio to read every email as English. On Malay mail its English model labelled
ordinary phrases as people ("Saya ingin", "cuti tahunan", "diserahkan", "perhatian anda", all at 0.85)
and still missed the name in the signature ("Nurul Huda"); on Chinese mail it found no names at all.
Hiding prose made the drafts and translations worse (the model never saw "annual leave"), and missing
names is a privacy failure.

## Scope

- **Name shapes as Presidio ad-hoc recognizers** (`listener/nameshapes.go`), matching
  `backend/app/core/name_patterns.py`: Malay patronymics (bin, binti, a/l, a/p, anak), hereditary
  prefixes (Tengku, Syed, Wan), common given-name leads (Muhammad, Nurul, Siti), and Chinese names: a
  common surname character and one or two more, where a name goes (before 先生/小姐/经理, after 我是,
  联系, 请, 致, or alone on a line as a sign-off). Words that start with a surname character but are not
  names (谢谢, 周三, 方便) are excluded.
- **Name, place and organisation hits narrowed to name-shaped runs:** capitalised words that are not
  common Malay or job and department words, or Chinese characters; a particle (bin, binti, van, de)
  joins two name words. "Saya ingin" and "cuti tahunan" drop out; "Farid" and "Nurul Huda" stay hidden.
  Other entities (phones, emails, accounts, cards) are untouched.
- **Over-masking stays the safe side:** a capitalised word the model calls a name and that is not on the
  Malay list is still hidden.

## Acceptance criteria

- [ ] Given the 13 Oct Malay leave request, then "cuti tahunan", "saya akan diserahkan", "perhatian anda"
      and "Yang benar" stay as written, and "Farid" and "Nurul Huda" are hidden.
- [ ] Given a Chinese email naming 陈伟明 after 我是, 李美玲 after 请联系, and 王小红 on the sign-off line,
      then all three are hidden and 会议时间 and 谢谢 stay.
- [ ] Given an English email, then names are hidden as before.
- [ ] Every pattern compiles in Presidio: a bad one fails the whole request, which would quarantine mail.

## Decisions

- 2026-10-13: Filter by the span's shape rather than by which recognizer found it: Presidio's response
  does not say, and the shape rule works for both the model's hits and the patterns'.
- 2026-10-13: Stored emails keep their old masking until re-read with `go run . reprocess`, which needs
  the owner's yes.
