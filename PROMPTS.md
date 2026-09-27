# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-09-27 — Verified the is_featured field and badge; ran migrations, tests, and dev server

### Prompts
1. did you add the is_featured field?
2. run the migrations and tests
3. run the dev server so I can see the badge
4. are the badge featured in two places, the catalog listing and product detail page confirmed?
5. stop the dev server
6. is MAP.md file not working in the other terminal i keep getting errors
7. Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including any corrections. End the entry with a short summary: the outcome, any places where I deviated from a recommended answer or asked follow-up questions, and anything that went sideways.

### Summary
- **Outcome:** No code changed. Confirmed from git history that
  `is_featured` (commit `d99592a`, migration `0003`) and the Featured badge
  (commit `8826ff6`) came from an earlier session, not this one. `migrate`
  had nothing to apply; `pytest` passed 169/169. Ran the dev server, and
  checked the served HTML to confirm the badge shows on the catalog listing
  and on the detail pages of the three featured products
  (seraphine, soulsear-mark-i, soulsear-mark-ii) and does not show on a
  product that isn't featured. Stopped the server and confirmed port 8000
  was free.
- **Deviations:** Prompt 2 followed the agent's suggestion to run
  `migrate` and `pytest`. Prompt 4 was a follow-up asking for explicit
  confirmation of both badge locations after the agent reported them; the
  agent re-checked each product instead of repeating its earlier answer.
  The agent noted that pytest ran on Python 3.14.7 while CLAUDE.md says
  3.13; this was not followed up. For MAP.md, the agent asked for the exact
  command and error text, which was not provided. The agent also declined
  to fill in MAP.md, since the assignment says to write it in your own words.
- **Sideways:** The first badge check requested `/products/`, which is not
  the catalog URL (the catalog is at `/`), and found no badges; it then
  found the right URL in `products/urls.py`. Page 1 of the catalog shows no
  badges because the featured products fall on pages 2 and 3 (12 per page),
  which could look like a bug on first view. The server log printed
  "Stopped watching for changes," but the server kept responding. The
  MAP.md errors were never diagnosed: the file is a valid Markdown
  template, and the likely cause (trying to run it as a command or with
  `python`) was not confirmed.
