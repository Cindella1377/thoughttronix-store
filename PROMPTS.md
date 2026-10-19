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

## 2026-10-18 — Designed product reviews with galaxy ratings; wrote the PRD and a nine-phase plan

### Prompts
1. /grill-me the site needs a review for products this would be in the product page for confirmed buyers it also has a rating system but lets not do start since that is for other things let make them galaxys 5 of them so if it is 5 its out of this world. for the soulsear owners they can but not next of kin to create a reiew. Customers can edit and delete there own review. staff can edit and delet any review. This process doesn't reload the page or cause the customer to lose their place.
2. B delivered only
3. A one per customer per product
4. b with option of photo upload if desired
5. A
6. c if they bought it and sent it back that doesn't count it disqualifies that option to review
7. c
8. b
9. B use those
10. b
11. c
12. c
13. b
14. a yes but include the date with the review as well
15. b
16. c
17. a
18. yes write the PRD
19. yes run prd-to-plan
20. what does merging phases do?
21. yes that order works write the plan and promts.md

### Summary
- **Outcome:** No code changed. A sixteen-question `/grill-me` interview
  settled the design: only Delivered buyers review, one review per
  customer per product, galaxies 1–5 (Black hole, Space junk, Low orbit,
  Stellar, Out of this world), optional text and one optional photo,
  reviews removed when their purchase stops being Delivered, in-place
  HTMX write/edit/delete with an inline delete confirm, staff moderation
  inline plus a back-office Reviews list, per-case messages in the form's
  place, an "edited" / "edited by ThoughtTronix staff" marker, a
  "Confirmed buyer · bought Mon YYYY" badge, ten per page with "Show
  more", galaxies on catalog cards, live publishing with no approval
  queue, and seeded samples including a pre-recall SoulSear Mark I
  review. Wrote `prd/reviews.md` and `plans/reviews.md` (nine phases).
  Nothing was committed.
- **Deviations:** Question 3 chose optional text (B) over the recommended
  required text, and added an optional photo; Question 4 then settled on
  one photo. Question 5 chose deleting a review when its purchase is
  returned (C) over the recommended keep-it rule (A). Question 13 accepted
  the recommendation but asked for a date on each review, which became
  Question 14 (posted date plus a bought-month badge). Every other answer
  took the recommended option. Prompt 20 was a follow-up asking what
  merging phases does; the agent explained, recommended keeping nine
  phases and moving "Returns remove reviews" up to Phase 3, and that order
  was approved.
- **Sideways:** "SoulSear owners, but not next of kin" was read as "the
  review belongs to the account that placed the order"; the agent stated
  that reading in the first question and it was never corrected, so it
  went into the PRD as written. The PRD notes two gaps the design leaves
  open: a status changed in Django's admin site does not remove reviews,
  and the seeded $1.2M Mark I order will show in long dashboard ranges.
  No tests or Ruff were run, since no code changed.

## 2026-10-18 — Restored the stray draft plan; designed and built wishlists in eight phases

### Prompts
1. i have a PRD and plan but it saved one level outside of my reporsitory on local instead of thoughtrnix-stor\prd why is this and can you fix it?
2. i approve if you can copy and bring it back that would be helpful
3. yes commit it
4. push it
5. /grill-me Add customer wishlist under there profile login. They have the ability to share it and add/remove if they want to update without relading the page unless shared only visible to the owner. the add/remove button is only on the product detail page but can have a "genie lamp" on the thumbnail which is smail just the icon  in the catolog to add to wishlist.
6. I like A and B
7. I like A1 because you can have your public wishlist and still have your link sent on or off control its a way to get others to the site kinda like PR in away brings people to come to the site so they would have to sign up would be the benifit
8. A, anyone can view but need account to buy
9. B the thumbnail genuie lamp is a default to the main list that is assigned
10. A, they can pick which list is main
11. A, each list has its own switches
12. b
13. B the genuie lamb is normal and when clicked it has smoke coming out of it also
14. A, outline lamp turns gold with smoke
15. C, both
16. C, both
17. a
18. b
19. a
20. a
21. A staff isn't odd that is another recommendation if they choice to display it for items they like if someone buys from there recommendation create a dashboard point system simple  that only staff or admin can see
22. B, separate follow-up feature
23. A
24. b i like this because what is public shouldn't matter if they want to be on a searching binge
25. a
26. b
27. a with B newest first default with the option of owner drags items if they want to change view order
28. b
29. a but it shows it was added automaticly is not hidden this wasn't a user choice unless they add it themself so it would have to have a difference
30. A user can remove sample if they dont support it if desired
31. yes write the prd
32. commit it and write the plan
33. can we do a pytest to see if it works?
34. keep it as listed, write the plan
35. commit and push it implement
36. yes please
37. add the session to PROMPTS.md

### Summary
- **Outcome:** The stray file one folder above the repo,
  `C:\Users\saman\cidm3312\account-security-draft.md`, was the draft plan
  removed in `05f884a`. It was moved back to
  `plans/account-security-draft.md`, committed, and pushed. A grill-me
  interview then produced `prd/wishlists.md` and `plans/wishlists.md`
  (eight phases), and all eight were built and pushed, one commit per
  phase, in a new `wishlists` app. Shoppers keep up to 20 named lists,
  with "My Wishlist" created on first save and starred as main. A genie
  lamp on catalog thumbnails toggles the main list, turning gold with a
  CSS smoke puff. The product page has a main button and a "Save to…"
  dropdown. The owner's list page has ✕ and ↑/↓ buttons. Each list has a
  "Share by link" switch (a new token each time it is turned on) and a
  "Show on my public page" switch for `/wishlist/<username>/`. The
  account page gained an optional first-name form, and `seed` makes
  badged sample lists. The suite went from 326 to 435 tests, all green,
  with Ruff clean.
- **Deviations:** The user went against the recommendation several
  times. On sharing they chose both the private link and the public
  page, as two independent switches (prompts 6–7), over a single
  three-level setting. They chose several named lists over one list
  (9), and the one-button-plus-dropdown product control over per-list
  checkboxes (12). They made the lamp a toggle with smoke (13), not
  add-only, and chose a friendly public page for real users over the
  one that hides whether an account exists (24). They chose a new link
  each time over a separate "Get a new link" button (17). Their reasons
  for the public page were PR and sign-ups. Drag-to-reorder (27) would
  have broken the HTMX-only rule, so they took ↑/↓ buttons instead (28).
  Sample lists had to be visibly marked as not the owner's choice
  (29–30). Staff wishlists became a future staff-picks points feature,
  split into its own PRD (21–22). Showing the owner's first name
  needed a first-name form on the account page, because no page set
  one; the user approved adding it (18–19).
- **Sideways:** Why the draft landed outside the repo was never proven.
  Its timestamp matched the commit that added it to `plans/`, which
  suggests a tool started in the parent folder. The first delete of the
  stray file was blocked by the permission check until the user
  approved it. During the build, one shell command failed to parse
  because of quoting and was rerun from a script file. In the browser
  check, the automation tool's mouse clicks never reached the page (no
  click events registered at all), so the lamp toggle was confirmed with
  a script click. The user has not yet tried it with a real mouse.
  `db.sqlite3` is changed by the migration and the reseed and remains
  uncommitted.

## 2026-10-10 — Tried to plan an account-security PRD that was never on disk

### Prompts
1. /prd-to-plan @prd/account-security.md
2. 1
3. saved it to prd/account-security.md
4. saved it again, check prd/account-security.md now
5. Save a summary of your session in PROMPTS.md

### Summary
- **Outcome:** No plan was written and no code changed. The skill needs a
  PRD in context, and `prd/account-security.md` did not exist at any of
  the three checks. The agent read the current `accounts` app (model,
  forms, views, URLs) and `plans/account-email-slices.md` so the
  exploration step is done for when the PRD arrives. This entry is the
  only file changed.
- **Deviations:** The agent offered three readings of the missing file: a
  new PRD not yet saved, `prd/account-email.md` under its draft name, or a
  PRD still to be written. Prompt 2 chose the first. The agent twice
  recommended pasting the PRD text into the chat instead of saving again;
  prompt 4 saved again instead. Prompt 5 asked for this log in different
  words from the standard session-log prompt; the agent used the standard
  entry shape.
- **Sideways:** The file was reported saved twice and was missing both
  times; `prd/` still held its four files, the newest from 15:48. A search
  of the home folder for documents saved in the last 30 minutes (skipping
  `AppData` and anything deeper than six folders) found no PRD. The only
  account-security file found was `C:\Users\saman\cidm3312\account-security-draft.md`,
  one folder above the repo: a byte-for-byte copy of the draft plan
  removed in `05f884a`, written against `prd/account-email.md`, not a PRD.
  Why the saves did not land was never diagnosed.

## 2026-10-10 — Designed and built account email, password reset, and password change

### Prompts
1. yes /grill-me
2. needs a provided an email when account is created, ability for them to reset there password when forgotten, can change there password if wanted.
3. A, required and unique
4. A, no exemption
5. B, console by default with .env switch
6. b, frees up the staff because when you get alot of costermer it would be a full-time job just fixing them
7. A, re-enter the current password
8. A, username only but using email address can sent them there username
9. B, 1 hour
10. B, notify the old address
11. B, prefill it but still editable
12. A, write the PRD then the plan
13. build phase 1 of the plan
14. build phase 2 of the plan
15. build phase 3 of the plan
16. build phase 4 of the plan
17. build phase 5 of the plan
18. run the dev server so I can see the account page
19. stop the dev server
20. Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including any corrections. End the entry with a short summary: the outcome, any places where I deviated from a recommended answer or asked follow-up questions, and anything that went sideways.
21. I viewed and all looks correct and running

### Summary
- **Outcome:** A ten-question grill-me interview produced
  `prd/account-email.md` and `plans/account-email.md`, and all five phases
  of the plan were built. Signup requires an email that is unique ignoring
  case (model constraint and migration `accounts/0002`). The sign-in page
  links to a password reset by emailed link, valid once and for one hour,
  which also states the username. A new account page, reached from
  "Hi, username", lets a signed-in user change their email (current
  password required, notice sent to the old address) and their password.
  Checkout prefills the account email. Mail settings read from `.env` and
  default to printing in the dev-server terminal. `CLAUDE.md` and
  `README.md` were updated. The suite went from 294 to 326 tests, green
  at every phase boundary, with Ruff clean. Nothing was committed; the
  work is uncommitted on `main`.
- **Deviations:** One recommendation was overridden. On whether to have
  an account page (prompt 6), the agent recommended a navbar
  "Change password" link only, with staff fixing emails in the admin
  site; the answer was the account page with self-service email editing,
  so staff are not tied up fixing emails as customers grow. Every other
  answer matched the recommendation. Prompt 8 added that the email
  address can be used to send customers their username; the agent read
  this as the reset email stating the username, with no separate
  "forgot my username" page, and said so. No follow-up questions were
  asked. The agent filled in details that were not discussed and listed
  them after writing the PRD: an unchanged email is refused, the notice
  does not state the new address, there are no separate "done" pages,
  the email change is a model method, and the URL layout.
- **Sideways:** `/grill-me` first ran with only "yes" and no plan to
  grill, so the agent searched the repo, found none, and asked for one.
  In Phase 2 a long shell heredoc failed to parse and wrote nothing; the
  agent moved the edits into a script file. Printing a real reset email
  then showed that Django's console backend split the reset link across
  two lines with a stray `=`, so it could not be copied from the
  terminal; the agent added a small console backend (`config/mail.py`)
  that was not in the plan, with a test and a sentence in the PRD. The
  link-expiry test also departed from the plan: it builds links 59 and
  61 minutes old instead of overriding the timeout setting. Two test
  edits were written wrong and fixed before the suite ran green: a
  mangled regex escape in Phase 2, and a stray test parameter in Phase 3
  that a `sed` command failed to remove. Stopping the dev server ended
  the background task but left the server answering on port 8000; the
  agent listed the leftover processes, confirmed they all came from its
  own launch, and ended the process tree. The agent never opened the new
  pages in a browser in any phase, did not run the plan's fresh-clone
  check, and sent no real mail through a provider. The dev server was
  started for the account page to be viewed by hand; after the log was
  first written, the user reported having viewed it and that all looked
  correct and was running (prompt 21). Applying the migration left the tracked
  `db.sqlite3` grading snapshot modified and uncommitted.

## 2026-10-04 — Designed product photos in a grill-me interview; wrote the PRD, plan, and handoff

### Prompts
1. /grill-me I need to include photos for the catolog protuct. There are two parts needed one with real images and the other a standard baseline placeholder. The photos are located in file named product-images to use.
2. A, go with the ImageField
3. A, exact matches only
4. A, the clean No Text photo
5. A, commit product-images and seed copies into media
6. B, shrink the sources once, JPEG is fine
7. B, and 2 MB is fine
8. A, leave them
9. B, the square box
10. B, add the thumbnail to the back-office product list
11. A, keep the per-category placeholders
12. A, write the PRD then the plan
13. create .claude/skills/handoff/SKILL.md and i'll add the text
14. /handoff the next session implements the design we just agreed
15. commit the PRD, plan, and handoff
16. commit the handoff skill too are the session logs bring written in prompts.md?
17. fix those two lines and commit
18. Append a session log to PROMPTS.md

### Summary
- **Outcome:** No application code changed. An eleven-question interview
  settled the product photos design: an `ImageField` on `Product`, photos
  only for exactly matching products, the clean SyncRest photo, committed
  JPEG sources that `seed` copies into a gitignored `media/`, staff upload
  with a 2 MB limit, a square catalog image box, a back-office thumbnail,
  and the existing per-category placeholders as the fallback. The agent
  wrote `prd/product-images.md`, `plans/product-images.md`, and
  `HANDOFF.md`, and created an empty `.claude/skills/handoff/SKILL.md`
  that the user filled in. Three commits were made on a new
  `product-images` branch (`d473a00`, `4baa366`, `89b0bc4`); nothing was
  pushed. `product-images/` is still untracked.
- **Deviations:** None from the recommendations: every answer in prompts
  2–12 chose the option the agent recommended. Several questions also
  asked whether the homework wording said anything specific (uploads
  versus static files, a single placeholder); those parts were never
  answered, so the design rests on the agent's reading of the request.
  Prompt 16 was a follow-up asking whether the session was being logged
  here; it was not, because this file's rules forbid unprompted entries.
  Prompt 18 was a shortened form of the session-log prompt.
- **Sideways:** The agent wrote the plan's Phase 5 and the handoff before
  reading this file's header, and both told a later agent to append to
  `PROMPTS.md` by itself; the handoff also listed this session's prompts
  for the next session to log. The agent caught this when answering
  prompt 16, and prompt 17 had both lines corrected. The first commit
  went onto a new `product-images` branch the user had not asked for,
  where earlier commits all went to `main`; the agent reported it and the
  user did not object. The PRD's product slugs were worked out by reading
  the product names, not by running `slugify`. The user moved to the
  handoff without saying whether they had read the PRD and plan, so the
  handoff asks the next session to confirm them first. Three details in
  those documents went beyond the literal answers: the original PNGs stay
  in place behind a `.gitignore` rule, the JPEGs keep the original file
  names, and the fallback lives in one `Product.image_url` property.

## 2026-09-27 — Stopped the dev server; committed the source.css safelist and the Homework 4 reflection

*Continues the coupon session logged in the two entries below; these are
the prompts given after the most recent one was written.*

### Prompts
1. commit and push it
2. stop the dev server
3. commit the source.css change
4. push it
5. commit the REFLECTION.md change
6. push it
7. write a session log for prompts.md

### Summary
- **Outcome:** No application code changed. The previous session log was
  committed and pushed (`9141f5a`). The dev server on port 8000 was
  stopped: before stopping it, the agent confirmed it was this project's
  `manage.py runserver`, stopped both the auto-reloader and its server
  process, and checked that port 8000 was free with no `runserver` left.
  `assets/css/source.css` had carried an uncommitted change through the
  whole session. Its diff turned out to be an `@source inline`
  safelist for `alert-{success,info,warning,error}`, because `base.html`
  builds those class names from message tags when the page renders. It
  was committed (`e6a2244`) and pushed. `REFLECTION.md` gained the Homework 4
  answers, written by the user during the session. The agent read the
  diff and committed it word for word (`a970ac9`), without editing, then
  pushed it. The working tree is clean and `main` matches GitHub.
- **Deviations:** None. Each commit was pushed only when asked, and the
  agent read each diff before writing a commit message for a change it
  hadn't made.
- **Sideways:** The dev server was not one the agent started. It was
  the user's own, most likely in the other terminal, so stopping it also
  ended the server in that terminal; the agent warned about this before
  stopping it. Its process IDs had changed since earlier in the session,
  so it had been restarted at some point; the agent re-identified the
  process instead of reusing the old IDs. The `REFLECTION.md` commit
  carries the agent's `Co-Authored-By` line even though the agent wrote
  none of that text.

## 2026-09-27 — Viewed the coupons in the dev server; showed a swapped-out coupon faded beside its replacement

*Continues the coupon session logged in the entry below; these are the
prompts given after that entry was written.*

### Prompts
1. commit and push it
2. run the dev server so I can see the coupons
3. on customer user - the code summer5 is working i thought it was expired
4. yes can we make a change to show the swap coupon as faded with the expired so it doesn't get confusing when it isn't the same coupon in the cart part
5. yes perfect!
6. push it
7. write a session log for prompts.md

### Summary
- **Outcome:** The previous session log was committed and pushed
  (`e996d68`). A dev server for this project was already running on port
  8000, most likely from the other terminal, so the agent used it
  instead of starting a second one. In the browser, SUMMER5 looked like it
  was working even though it had expired. Checking the database showed the
  swap working as designed: SUMMER5 had been replaced with SAVE15, whose
  $15.00 saving was closest to SUMMER5's $5 among the public coupons
  (WELCOME5 was excluded because `customer` had already used it). The
  coupon line showed only SAVE15, though, which read as SUMMER5 being
  accepted. The fix: the cart now records the swapped-out coupon and why
  (`replaced_coupon` and `replaced_coupon_status`, migration `0006`) and
  shows it struck through and faded with an arrow to the replacement
  (`~~SUMMER5~~ Expired → SAVE15`). The faded code stays after the notice
  is dismissed and clears on applying another code, removing the coupon,
  or checking out. The coupon PRD was updated to match. The suite went
  from 277 to 279 tests, all passing. It was committed (`08946e7`) and
  pushed.
- **Deviations:** Prompt 3 reported what looked like a bug. The agent
  explained it was the swap chosen during grilling (question 11, "swap it
  the same way") and offered two options: make the swap easier to see, or
  reject typed-in expired codes (question 11's option B). Prompt 4 chose
  making the swap easier to see, in its own form: the faded original
  code. The agent decided some details itself and stated them: the faded
  code stays after the notice is dismissed; with no replacement, it shows
  on its own; and it has a reason label ("Expired", "Already used", "Not
  running").
- **Sideways:** The first version of the change worked out the reason
  label from today's date when the page was shown. The agent noticed this
  could disagree with the actual reason for the swap, such as an
  "Already used" coupon later expiring, and switched to storing the label
  when the swap happens, before running any tests. Ruff flagged the import
  spacing above the new `COUPON_FIELDS` constant; `ruff check --fix`
  resolved it. `tailwind build` reported "up to date" even though the new
  `line-through` and `sr-only` classes were missing from the compiled CSS;
  a check of the stylesheet caught this, and `tailwind build --force`
  fixed it. The customer's cart had been swapped before the new fields
  existed, so it didn't show the faded code until SUMMER5 was entered
  again. The new layout was verified through the HTML in tests, not by the
  agent viewing it in a browser. In prompt 5 the user approved the change
  after reading the agent's summary of it.

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
