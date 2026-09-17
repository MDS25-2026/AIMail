"""Generate the static study site for GitHub Pages.

Writes a single self-contained index.html into the survey repo. Only participant-facing content
is emitted — gold labels stay in this repo, because the survey repo is public and a participant
following the link must not be able to find the answers.

Wording is the Lane B owner's, taken from the Microsoft Forms draft, not regenerated from the
markdown instrument. The two will drift; this file is the one that ships.

Responses POST to Supabase. The URL and anon key live in the survey repo's config.js, never here:
the anon key is public by design, but it is deployment configuration rather than something this
repo should carry.

Usage (from backend/):
    python scripts/build_study_site.py --out ../../survey/index.html
"""

import argparse
import asyncio
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_study_instrument import (
    EXPLAIN_POSITIONS,
    PART1_ROWS,
    load_drafts,
    read_holdout,
    readable_email,
    select_drafts,
)

TITLE = "Sorting Work Emails by Urgency"
BYLINE = "by MDS25, Monash University"

INTRO = """We are a Final-Year Project group building an email assistant that sorts mail by how
urgently it needs attention, and want to know how you would sort the same emails, so we can tell
whether the system's judgement is reasonable."""

CONTEXT = """<p><strong>What you need to do:</strong> Read 9 emails and sort each as high, medium
or low urgency, then rate a few AI-written replies. About 20 minutes.</p>

<p>These emails are from Enron, an American company based in Houston, Texas, written between
roughly 1999 and 2001. At the time it was one of the largest companies in the United States with
around 20,000 employees, and offices across America, Europe and Asia.</p>

<p><strong>What the company did:</strong> Enron began as a natural gas pipeline business. By the
time these emails were written it had become mainly an energy trading company, with physical assets
like pipelines and power plants.</p>

<p>The archive holds the mailboxes of roughly 150 employees, mostly traders and their managers in
the Houston gas and power groups. So most of what you will read is one colleague writing to another
about a deal, a report, a meeting, or an approval someone needs. A few are newsletters or automated
notices from internal systems.</p>

<p>The company collapsed at the end of 2001. A US regulator released these emails during the
investigation that followed.</p>

<p><strong>Read each one as the person who received it:</strong> an employee at that company, going
through their own work inbox on a normal working day.</p>

<p class="note">We do not collect your name, email address or any other identifying detail.
Responses are numbered, not named. You can stop at any time. Summary figures go in our report; raw
responses do not, and they are deleted once it is submitted.</p>"""

PART1_INTRO = """<p>You will read 9 emails. For each one, decide how urgently it needs the
recipient's attention.</p>

<p><strong>Use your own judgement.</strong> Sort them the way you would your own inbox.</p>

<p>These are real emails pulled from an archive exactly as they were stored. Some show who sent
them and a subject line; some are just the message. Some are forwards with the older thread
underneath. Judge each on what is actually in front of you; if you cannot tell who sent it, that is
part of the situation.</p>

<p>You may choose "Other" if you have the time to explain any particular reasoning.</p>"""

PART2_INTRO = """<p>Here are replies our system drafted automatically. The email it was replying to
is shown first, then the draft.</p>

<p>For each one you will answer four quick checks and then an overall verdict. The four checks are
the same ones our system runs on itself &mdash; we want to know where your judgement and its
judgement differ, not just whether they agree overall.</p>

<p>Personal details were removed before the AI ever saw these emails, so you may see placeholders
like <code>[EMAIL_REDACTED]</code>.</p>"""

EXPLAIN_LABEL = "In 1 or 2 sentences, what was the reasoning for your decision in the previous question?"

CLOSING = [
    ("q1_not_fitting",
     "Did any of the emails not fit into high, medium or low? If yes, which one, and what was missing?"),
    ("q2_sender_list",
     ("Imagine you could mark certain senders as important, so mail from them was always treated "
      "as urgent. Would that have changed how you sorted any of the emails above? If yes, which "
      "ones, and why?")),
]

GATES = [
    ("g1", "Does the reply state anything that is not in the email above?",
     "Made-up facts, dates, names, or promises that were never mentioned.",
     ["No, everything in it traces back to the email", "Yes, it invents something", "Not sure"]),
    ("g2", "Does the reply give away any personal details it should not?",
     "A phone number, email address, ID number, or someone else's name.",
     ["No", "Yes", "Not sure"]),
    ("g3", "Is the tone right for a work reply?", "",
     ["Yes", "Too formal", "Too casual", "Something else is off"]),
    ("g4", "Does the reply answer everything the email asked?", "",
     ["Yes, all of it", "It misses part of it", "It misses most of it"]),
    ("send", "Overall: would you send this as written?", "",
     ["Yes", "Only after editing", "No"]),
]


def esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def radio_group(name: str, options: list[str], *, required: bool = True) -> str:
    req = " required" if required else ""
    rows = "\n".join(
        f'      <label class="opt"><input type="radio" name="{name}" '
        f'value="{esc(option)}"{req}><span>{esc(option)}</span></label>'
        for option in options
    )
    return f'    <div class="opts">\n{rows}\n    </div>'


def question(number: int, label: str, body: str, *, hint: str = "") -> str:
    hint_html = f'\n    <p class="hint">{esc(hint)}</p>' if hint else ""
    return (f'  <fieldset class="q">\n'
            f'    <legend><span class="num">{number}</span>{esc(label)}</legend>{hint_html}\n'
            f'{body}\n  </fieldset>')


def email_block(text: str) -> str:
    return f'    <pre class="email">{esc(text)}</pre>'


def render_part1(items: dict[int, tuple[str, str]], counter: list[int]) -> str:
    blocks = []
    for position, (row, _) in enumerate(PART1_ROWS, 1):
        body, _gold = items[row]
        # "Other" goes on items with no follow-up, so every item has some route for a participant
        # who thinks none of the three fit. Matches the Forms draft exactly.
        has_other = position not in EXPLAIN_POSITIONS
        options = ["High", "Medium", "Low"] + (["Other"] if has_other else [])
        inner = email_block(readable_email(body)) + "\n" + radio_group(f"item_{position}", options)
        if has_other:
            inner += (f'\n    <input type="text" class="other" name="other_{position}" '
                      f'placeholder="If Other, please say how you would describe it">')
        counter[0] += 1
        blocks.append(question(counter[0], f"Email {position} of 9", inner))

        if position in EXPLAIN_POSITIONS:
            counter[0] += 1
            field = (f'    <input type="text" name="explain_{position}" '
                     f'placeholder="Your answer" required>')
            blocks.append(question(counter[0], EXPLAIN_LABEL, field))
    return "\n".join(blocks)


def render_closing(counter: list[int]) -> str:
    blocks = []
    for name, label in CLOSING:
        counter[0] += 1
        blocks.append(question(
            counter[0], label,
            f'    <input type="text" name="{name}" placeholder="Your answer" required>'))
    return "\n".join(blocks)


def render_part2(drafts: list[dict], counter: list[int]) -> str:
    blocks = []
    for position, row in enumerate(drafts, 1):
        parts = ['  <div class="draft">',
                 f'    <h3>Reply {position} of {len(drafts)}</h3>',
                 '    <p class="label">The email that was received</p>',
                 email_block(readable_email(row["body_masked"])),
                 '    <p class="label">The draft reply</p>',
                 email_block(readable_email(row["draft_reply"])),
                 '  </div>']
        blocks.append("\n".join(parts))
        for key, label, hint, options in GATES:
            counter[0] += 1
            blocks.append(question(counter[0], label,
                                   radio_group(f"{key}_{position}", options), hint=hint))
        counter[0] += 1
        blocks.append(question(
            counter[0], "If not as written, what would you change?",
            f'    <input type="text" name="comment_{position}" placeholder="Optional">'))
    return "\n".join(blocks)


def render(items: dict[int, tuple[str, str]], drafts: list[dict]) -> str:
    counter = [0]
    counter[0] += 1
    consent = question(counter[0], "Do you consent to take part on this basis?",
                       radio_group("consent", ["Yes", "No"]))
    counter[0] += 1
    experience = question(
        counter[0], "How much experience do you have managing a work or professional email inbox?",
        radio_group("role", ["Little or none",
                             "Some: an internship, part-time or casual work",
                             "Regular: it is part of my current work",
                             "Heavy: I deal with a large volume of work email daily"]))
    part1 = render_part1(items, counter)
    closing = render_closing(counter)
    part2 = render_part2(drafts, counter) if drafts else ""
    part2_section = (f'<section>\n  <h2>Part 2: Rating AI-written replies</h2>\n'
                     f'{PART2_INTRO}\n{part2}\n</section>') if drafts else ""

    return TEMPLATE.format(
        title=esc(TITLE), byline=esc(BYLINE), intro=esc(INTRO),
        context=CONTEXT, consent=consent, experience=experience,
        part1_intro=PART1_INTRO, part1=part1, closing=closing,
        part2_section=part2_section,
    )


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{title}</title>
<style>
  :root {{ --ink:#1c1c1e; --muted:#6b6b70; --line:#dcdce0; --bg:#f7f7f8; --accent:#0b5cad; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 -apple-system,
         BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:24px 16px 96px; }}
  header {{ border-top:5px solid var(--accent); background:#fff; border:1px solid var(--line);
            border-radius:10px; padding:24px; margin-bottom:20px; }}
  h1 {{ margin:0 0 4px; font-size:26px; line-height:1.25; }}
  .byline {{ color:var(--muted); margin:0 0 14px; }}
  h2 {{ font-size:20px; margin:0 0 12px; }}
  section {{ background:#fff; border:1px solid var(--line); border-radius:10px; padding:24px;
             margin-bottom:20px; }}
  .q {{ border:0; border-top:1px solid var(--line); margin:20px 0 0; padding:18px 0 0; }}
  .q legend {{ font-weight:600; padding:0; display:block; width:100%; }}
  .num {{ display:inline-block; min-width:26px; color:var(--muted); font-weight:500; }}
  .hint {{ color:var(--muted); margin:4px 0 0 26px; font-size:14px; }}
  pre.email {{ white-space:pre-wrap; word-wrap:break-word; background:#fbfbfc;
               border:1px solid var(--line); border-left:3px solid #c3c3c8; border-radius:6px;
               padding:14px; margin:12px 0 14px 0; font:13px/1.55 ui-monospace,SFMono-Regular,
               Menlo,Consolas,monospace; max-height:none; }}
  .opts {{ display:flex; flex-direction:column; gap:2px; }}
  label.opt {{ display:flex; align-items:flex-start; gap:10px; padding:8px 10px; border-radius:6px;
               cursor:pointer; }}
  label.opt:hover {{ background:#f2f6fb; }}
  label.opt input {{ margin-top:5px; flex:0 0 auto; }}
  input[type=text] {{ width:100%; padding:10px 12px; border:1px solid var(--line);
                      border-radius:6px; font:inherit; margin-top:8px; }}
  input[type=text]:focus {{ outline:2px solid var(--accent); outline-offset:1px; }}
  .draft h3 {{ margin:26px 0 6px; font-size:17px; }}
  .label {{ color:var(--muted); font-size:13px; text-transform:uppercase; letter-spacing:.04em;
            margin:14px 0 0; }}
  .note {{ color:var(--muted); font-size:14px; border-left:3px solid var(--line); padding-left:12px; }}
  button {{ background:var(--accent); color:#fff; border:0; border-radius:8px; padding:14px 26px;
            font:600 16px/1 inherit; cursor:pointer; }}
  button:disabled {{ opacity:.55; cursor:default; }}
  #bar {{ position:fixed; left:0; top:0; height:3px; background:var(--accent); width:0;
          transition:width .2s; z-index:9; }}
  #done, #fallback {{ display:none; }}
  #fallback textarea {{ width:100%; height:190px; font:12px/1.5 ui-monospace,monospace;
                        margin-top:10px; }}
  @media (max-width:600px) {{ .wrap {{ padding:12px 10px 80px; }} section, header {{ padding:16px; }} }}
</style>
</head>
<body>
<div id="bar"></div>
<div class="wrap">

<header>
  <h1>{title}</h1>
  <p class="byline">{byline}</p>
  <p>{intro}</p>
</header>

<form id="study">

<section>
  <h2>Consent and context</h2>
  {context}
{consent}
{experience}
</section>

<section>
  <h2>Part 1: Sorting emails by urgency</h2>
  {part1_intro}
{part1}
{closing}
</section>

{part2_section}

<section>
  <p id="status" class="note" role="status"></p>
  <button type="submit" id="send">Submit my answers</button>
</section>

</form>

<section id="done">
  <h2>Thank you</h2>
  <p>Your answers have been recorded. You can close this page.</p>
</section>

<section id="fallback">
  <h2>Could not submit</h2>
  <p>Something went wrong saving your answers. Nothing is lost &mdash; copy the text below and send
     it to whoever gave you this link.</p>
  <textarea id="dump" readonly></textarea>
</section>

</div>
<script src="config.js"></script>
<script>
(function () {{
  var form = document.getElementById('study');
  var bar = document.getElementById('bar');
  var status = document.getElementById('status');
  var button = document.getElementById('send');

  function required() {{
    return Array.prototype.slice.call(form.querySelectorAll('[required]'));
  }}
  function answered() {{
    var names = {{}};
    required().forEach(function (el) {{
      if (el.type === 'radio') {{
        if (form.querySelector('input[name="' + el.name + '"]:checked')) names[el.name] = 1;
      }} else if (el.value.trim()) {{ names[el.name] = 1; }}
    }});
    return Object.keys(names).length;
  }}
  function total() {{
    var names = {{}};
    required().forEach(function (el) {{ names[el.name] = 1; }});
    return Object.keys(names).length;
  }}
  function progress() {{ bar.style.width = (answered() / total() * 100) + '%'; }}
  form.addEventListener('input', progress);
  form.addEventListener('change', progress);

  function collect() {{
    var out = {{ submitted_at: new Date().toISOString() }};
    new FormData(form).forEach(function (value, key) {{ out[key] = value; }});
    return out;
  }}

  form.addEventListener('submit', function (event) {{
    event.preventDefault();
    var payload = collect();
    button.disabled = true;
    status.textContent = 'Sending...';

    if (!window.STUDY_CONFIG || !window.STUDY_CONFIG.url) {{
      show_fallback(payload, 'This form has not been connected to a database yet.');
      return;
    }}

    fetch(window.STUDY_CONFIG.url, {{
      method: 'POST',
      headers: {{
        'Content-Type': 'application/json',
        'apikey': window.STUDY_CONFIG.key,
        'Authorization': 'Bearer ' + window.STUDY_CONFIG.key,
        'Prefer': 'return=minimal'
      }},
      body: JSON.stringify({{ answers: payload }})
    }}).then(function (response) {{
      if (!response.ok) throw new Error('HTTP ' + response.status);
      form.style.display = 'none';
      document.getElementById('done').style.display = 'block';
      window.scrollTo(0, 0);
    }}).catch(function (error) {{
      show_fallback(payload, String(error));
    }});
  }});

  function show_fallback(payload, reason) {{
    button.disabled = false;
    status.textContent = '';
    document.getElementById('dump').value = JSON.stringify(payload, null, 2);
    document.getElementById('fallback').style.display = 'block';
    document.getElementById('fallback').scrollIntoView();
    if (window.console) console.error('study submit failed:', reason);
  }}
}})();
</script>
</body>
</html>
"""


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", default="holdout_to_label.csv")
    parser.add_argument("--out", default="../../survey/index.html")
    parser.add_argument("--part2-limit", type=int, default=6)
    parser.add_argument("--no-part2", action="store_true", help="skip the DB read")
    args = parser.parse_args()

    items = read_holdout(Path(args.holdout), [row for row, _ in PART1_ROWS])
    drafts: list[dict] = []
    if not args.no_part2:
        available = await load_drafts()
        drafts = select_drafts(available, args.part2_limit)
        print(f"  selected {len(drafts)} of {len(available)} draft(s) for Part 2")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(items, drafts), encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"  wrote {out} ({size:.0f} KB)")
    print("  contains no gold labels — safe for a public repo")


if __name__ == "__main__":
    asyncio.run(main())
