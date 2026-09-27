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

## 2026-09-27 — Fixed the grill-me skill, designed coupon codes by grilling, and built them in five phases

### Prompts
1. why am i still not seeing the grill-me?
2. yes, run it and commit
3. push it
4. /grill-me
5. I need to create a new feature with coupon codes that when expired doesn't give an error they are automaticly updated or cycled out leaving a prompt to the user that it has expired.
6. I like B but also like the scheduling option as well can we combine them?
7. i would do the swap so they dont get an error message and its replaced with the closest likeable coupon
8. lets do C so it always finds something
9. lets do C so we can do both
10. lets do A closest in dollars saved
11. A because it would put the customer first
12. A, bigger saving wins
13. A, save it on the cart
14. A, follow the chain
15. A, remove it and tell the customer
16. b i think user response is better flash message will be confusing if they see the code changed without knowing why especially if it is less than expired coupon
17. A, swap it the same way
18. b
19. A, keep it but pause it
20. C, store both
21. A, add a back-office tab
22. B, put it in services
23. B, limit per customer
24. B, start and end dates
25. C, pass now into the functions
26. yes, draft the prd and plan
27. yes, commit them, is there a rule one coupon per order?
28. push it
29. was this feature implemented?
30. yes, start phase 1
31. yes, commit it
32. phase 2
33. commit it
34. phase 3
35. commit it
36. phase 4
37. commit it
38. push it than phase 5
39. commit and push it
40. log the session in PROMPTS.md

### Summary
- **Outcome:** The grill-me skill was in `.claude/skill/` (singular), so
  Claude Code never found it; it was moved to `.claude/skills/grill-me/`
  and the case-only rename to `SKILL.md` was committed (`4548a1a`). A
  19-question grilling session designed coupon codes that swap an expired
  coupon for a replacement instead of showing an error. That design became
  `prd/coupons.md` and `plans/coupons.md` (`e8697b9`), then was built in
  five phases, each committed with the suite green: the `Coupon` model and
  `find_replacement` matching rule (`9c06b13`); coupons on the cart with
  three new HTMX endpoints and a stored swap notice (`a617cf5`); discounts
  charged and snapshotted on orders, with the `coupon_code` seam made live
  and the per-customer limit working (`2d9106c`); the back-office Coupons
  tab (`ea16d2c`); and demo coupons in the seed plus README and CLAUDE.md
  updates (`7734225`). The suite grew from 169 to 277 tests. Everything is
  pushed. `assets/css/source.css` had an unrelated uncommitted change the
  whole session and was left alone.
- **Deviations:** Of the 19 grilling questions, 9 went against the agent's
  recommendation. Expired coupons are replaced with a new one (B), not
  just removed (A), and prompt 6 asked whether that could be combined
  with scheduled cleanup. The agent explained that expiry could be worked
  out from dates with no background job, and prompt 7 never answered that
  question directly, so the agent assumed the no-job option. Other choices
  against the recommendation: staff link plus closest-match fallback (C,
  over A); both percent and fixed-amount discounts (C, over A); the
  nearest match in either direction, putting the customer first (A, over
  C); a swap notice stored on the cart rather than a flash message (B,
  over A), because a lower replacement would confuse customers without an
  explanation; an optional minimum order (B); order snapshot plus link (C);
  a per-customer limit (B); start and end dates (B); and passing `now`
  into functions (C). Follow-up questions: whether one coupon per order
  was a rule, which led to stating in user story 1 that a new code
  replaces the current one; and whether the feature had been implemented,
  which it had not at that point. The agent also made several decisions
  itself and flagged them each time: codes are case-insensitive; a coupon
  expires exactly at `expires_at`; placing an order clears the cart's
  coupon; a staff-chosen replacement below its minimum is applied paused;
  a coupon rescheduled into the future is swapped like an expired one;
  codes are letters, numbers, and hyphens only; and dates use the
  browser's date-time picker.
- **Sideways:** The first `git mv -f` for the case-only rename failed with
  "will not add file alias", yet it had staged the rename anyway, so the
  retry through a temporary name failed with "not under version control";
  checking `git status` showed the rename already staged, and it was
  committed. `/grill-me` first ran with no plan to grill, so the agent
  asked for one. In Phase 2 a Python heredoc edit to `orders/models.py`
  failed its own text-match check and wrote nothing; the agent switched to
  the Edit tool. Between Phases 2 and 3, checkout showed the discount in
  its summary while still charging full price; the Place order button
  showed the full price so it matched the charge. Two per-customer-limit
  tests were marked strict expected failures in Phase 1 until
  `Order.coupon` existed in Phase 3. A back-office tab test that depended
  on exact template whitespace was rewritten before it was run, and a
  notice with two "and"s was reworded. The new pages were never viewed in
  a browser; only their HTML was tested. A new seed test calls the seed
  command, as the existing seed tests already did, even though CLAUDE.md
  says tests never invoke it.

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
