# Implementation Plan (Draft): The ThoughtTronix Store — Account Security

*Companion to `prd/account-email.md`. The PRD owns the requirements; this plan owns the sequence. Where a task says "per the PRD," the PRD's wording is authoritative — do not improvise alternatives. The suite must be green at every phase boundary.*

*Each phase is written test-first: the tests named in a phase are written before the code they cover, and the phase ends only when they pass alongside the rest of the suite.*

---

## Phase 1 — The Email Rule

**Goal:** Every account carries an email that belongs to it alone, enforced by the database.

**Tasks:**
1. `conftest.py`: give the shared `customer` and `staff_user` fixtures distinct emails. Do the same for every test that creates a user inline (`orders/tests.py`, `orders/test_orders.py`). Run the suite before touching the model: still green.
2. Model tests — PRD coverage priority 1: two accounts cannot share an email, including when only the capitalisation differs.
3. `accounts.User`: redeclare `email` as a required `EmailField` and add the `UniqueConstraint` on `Lower("email")`, per the PRD. No exemption for a blank email.
4. One migration. Apply it to the local database and confirm the twelve existing users pass it with no data fix.
5. Seed data test — PRD coverage priority 8: every demo user's email is distinct ignoring case, read from the seed's constants without invoking the command.

**Verification.** *Automated:* model and seed data tests green; full suite green; Ruff clean. *Manual:* in the admin site, try to save a second user with an existing email in different capitals and see it refused; run `seed` and confirm it still builds the demo world.

**Out of bounds:** the signup form, mail settings, every password page, the account page, checkout.

---

## Phase 2 — Signup Collects the Email

**Goal:** A visitor cannot create an account without an email, and is told when the address is taken.

**Tasks:**
1. Form and view tests — PRD coverage priority 2: an email is required, a duplicate is rejected with an error on the Email field, and a valid signup stores the email.
2. `SignupForm`: add `email` with a `clean_email` that does the case-insensitive lookup, per the PRD. Correct any docstring that says signup takes no email.
3. `templates/accounts/signup.html`: confirm the Email field and its errors render; change the template only if it does not loop over the form's fields.
4. Confirm the post-signup redirect is still the sign-in page, with no auto-login.

**Verification.** *Automated:* signup tests green; full suite green. *Manual:* sign up with a new email and sign in; sign up again with the same email in different capitals and read the error beside the Email field.

**Out of bounds:** confirming the address by a link, signing in with an email, mail settings, every password page.

---

## Phase 3 — Mail and the Forgotten Password

**Goal:** A customer who forgot their password — or their username — gets back in through their email.

**Tasks:**
1. `config/mail.py`: the store's console backend, a small subclass of Django's that prints each email as written so a reset link is not split across lines.
2. `config/settings.py`: backend, host, port, username, password, TLS, and from-address read from `.env` through environs, defaulting to the console backend; `PASSWORD_RESET_TIMEOUT = 3600`. `.env.example`: list the mail settings. The app must still start with no `.env`.
3. Reset tests — PRD coverage priority 3, reading mail from Django's in-memory test mailbox. Expiry is tested by overriding `PASSWORD_RESET_TIMEOUT`, not by freezing the clock.
4. `accounts/forms.py`: DaisyUI-dressed subclasses of Django's password-reset and set-password forms.
5. `accounts/views.py` and `accounts/urls.py`: subclasses of Django's reset views at the names and paths in the PRD's table — `password_reset`, `password_reset_done`, `password_reset_confirm`. Success URLs are namespaced. A completed reset redirects to `accounts:login` with a success message; there is no separate "complete" page.
6. Templates in `templates/accounts/`, all extending `base.html`: the request page, the "check your inbox" page, and the confirm page, which shows the new-password form for a valid link and the expired-link state with a "request a new one" button for an invalid, expired, or used one.
7. Plain-text subject and body templates for the reset email, per the PRD: the store's voice, the username, and the link built from the namespaced URL name.
8. `templates/accounts/login.html`: a "Forgot your password?" link. Sign-in itself stays username-only.

**Verification.** *Automated:* reset tests green; full suite green. *Manual:* as a seeded customer, ask for a reset; copy the link whole from the dev-server terminal and check the email names the username; set a new password and land on sign-in with the success message; sign in with it; open the same link again and see the expired page and its button; ask for a reset with an address that has no account and see the same "check your inbox" page with nothing printed in the terminal.

**Out of bounds:** limiting how often resets can be requested, a notice email on reset, HTML email, a "forgot my username" page, auto-login after a reset, real SMTP delivery.

---

## Phase 4 — The Account Page

**Goal:** A signed-in user manages their own password and email without involving staff.

**Tasks:**
1. Model tests, then `User.change_email(new_email)` per the PRD: it saves the new address and sends one plain-text notice to the old one. The notice says the email was changed and to contact the store if that was unexpected; it does not include the new address. Subject and body templates alongside the reset email's.
2. Form tests, then `EmailChangeForm` per the PRD: new email plus current password, rejecting a wrong password, another account's address (case-insensitive), and the address the account already has. The form calls `change_email`; the view stays thin.
3. A DaisyUI-dressed subclass of Django's password-change form.
4. Account page view, URL (`accounts:account` at `/accounts/`), and `templates/accounts/account.html`: sign-in required; username, email, the change-email form, and a link to change password. No order history. A successful email change redirects back to the page with a success message.
5. Change-password view, URL (`accounts:password_change`), and template. Success redirects to the account page with a success message, keeps this session, and ends the user's other sessions.
6. `templates/base.html`: "Hi, username" becomes a link to the account page for every signed-in user.
7. View tests — PRD coverage priorities 4, 5, and 6.

**Verification.** *Automated:* model, form, and view tests green; full suite green. *Manual:* as a seeded customer, open the account page from the navbar; change the password, confirm the session survives, then sign out and in with the new one; change the email with a wrong password and read the error; change it correctly and read the notice to the old address in the terminal; try another seeded user's email and your own current one and see both refused; signed out, request the account page and land on sign-in; repeat the navbar check as a staff user.

**Out of bounds:** editing the username or name, a notice on password change, confirming a new address by a link, checkout.

---

## Phase 5 — Checkout Knows the Email

**Goal:** Checkout stops asking for an email the store already has, without changing what an order records.

**Tasks:**
1. Checkout tests — PRD coverage priority 7: the Email field is prefilled from the account, and an order placed with an overwritten address stores the overwritten one.
2. `CheckoutView`: supply the account email as the Email field's initial value. `CheckoutForm`, `Order.email`, and `orders/services.py` are not changed.

**Verification.** *Automated:* checkout tests green; the existing order and service tests untouched and green. *Manual:* as a seeded customer with a cart, open checkout and see the Email box filled; overwrite it, place the order, and confirm the order shows the overwritten address while the account page still shows the account's; change the account email and confirm the placed order's email does not move.

**Out of bounds:** removing the checkout Email field, any change to stored orders.

---

## Phase 6 — Documentation

**Goal:** The project's own records describe the feature.

**Tasks:**
1. `CLAUDE.md`: name the PRD and plan in the opening paragraph; in the project layout, describe `config/mail.py`, and update the `accounts/` entry to say email is required and unique ignoring case, that the app carries the account page and the password reset and change flows, and that `User.change_email` is the one place an email changes.
2. `README.md`: note that reset and notice emails print in the dev-server terminal by default, and which `.env` settings switch on real mail.
3. `PROMPTS.md`: append only when the session-log prompt is given; never rewrite earlier entries.
4. Final pass: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.

**Verification.** *Automated:* suite green, Ruff clean. *Manual:* from a fresh clone with no `.env`, `uv sync`, `migrate`, `seed`, and `tailwind runserver` give a store where signup asks for an email and a reset link appears whole in the terminal.

**Out of bounds:** anything in the PRD's Out of Scope section; committing the updated `db.sqlite3` snapshot without being asked.
