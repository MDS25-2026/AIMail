# Landing page: show the product working, then one way in

- **Status:** in progress 2026-10-12
- **Owner:** veyroxie; Lane D (Han) to review
- **Replaces:** the plain landing in `src/routes/signin.tsx` (headline, three pillars, four steps)

## Why

The deployed dashboard opens on `/signin` for anyone signed out, so this page is the first thing a
visitor, a judge or a supervisor sees. The best product pages answer three questions fast: what is
it, why trust it, what next. They show the product working in the hero instead of a tagline, keep
claims concrete, group features in a card grid, answer objections in an FAQ, and repeat the call
to action at the end.

## What it shows

1. **Header:** the name, a language switch (English, Bahasa Melayu, 中文; the same preference the
   app uses) and "Sign in with Google".
2. **Hero:** headline, one-line promise, the sign-in button, and a **live preview** beside it: a
   small AIMail window that plays the real flow in four stages. An email arrives with a name, an
   email address and a phone number; the details turn into placeholders ("What the AI sees"); a
   draft appears with the AI check badge; the reply is approved and goes out with the real name put
   back. The stage buttons under it can be pressed; it pauses on hover and focus; with reduced
   motion it never advances by itself. The sample person is fictional, with `example.com` and the
   standard dummy phone number.
3. **Trust strip:** four facts, each true today: details hidden before any AI reads them; nothing is
   sent until you approve; English, Bahasa Melayu and 中文; you can delete your data.
4. **Feature grid:** six cards: the privacy receipt, names you type hidden too, drafts grounded in your
   company's documents with sources shown, who still owes you a reply, send later and quiet hours,
   and Private mode on your company's own model.
5. **You see / the AI sees:** the same email side by side.
6. **How it works:** the existing four steps.
7. **FAQ:** does it send on its own (only opt-in holding replies), does the AI see names (no, with the
   honest limit), which AI, can I delete my data, which languages.
8. **Closing call to action** and the existing footer.

## Rules

- No testimonials, logos or numbers that are not real; no fabricated social proof.
- Every string in English, Malay and Chinese (Malay and Chinese to be checked by native speakers).
- Existing colour tokens only, so the palette check (contrast and colour-blind) still covers it.
- One `h1`; the sign-in error banner stays at the top of the hero.
