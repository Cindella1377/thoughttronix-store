# Implementation Plan: The ThoughtTronix Store — Account Email and Passwords

*Companion to `prd/account-email.md`. The PRD owns the requirements; this plan owns the sequence. Where a task says "per the PRD," the PRD's wording is authoritative — do not improvise alternatives. The suite must be green at every phase boundary.*

---

## Phase 1 — Every Account Has Its Own Email

**Goal:** No account can exist without an email of its own, and signup collects one.

**Tasks:**
1. `conftest.py`: give the `customer` and `staff_user` fixtures emails. Give emails to the users created inline in `orders/tests.py` and `orders/test_orders.py`. Run the suite: still green, before any model change.
2. `accounts.User`: redeclare `email` as required and add the case-insensitive unique constraint, per the PRD. Migration. Apply it to the local database and confirm it runs without a data fix.
3. Model tests — PRD coverage priority 1.
4. `SignupForm`: add `email` with `clean_email` per the PRD; update the docstring that says "No email". Form and view tests first — PRD coverage priority 2.
5. `templates/accounts/signup.html`: confirm the Email field renders with its errors; change the template only if it does not loop over the form's fields.
6. Seed data test — PRD coverage priority 8 — reading the seed's user constants directly.

**Verification.** *Automated:* model, form, and seed data tests green; full suite green; Ruff clean. *Manual:* sign up with a new email and sign in; try again with the same email in different capitals and read the error beside the Email field; in the admin site, try to save a second user with an existing email and see it refused.

**Out of bounds:** mail settings, every password page, the account page, checkout.

---

## Phase 2 — Forgotten Password

**Goal:** A customer who forgot their password gets back in through their email.

**Tasks:**
1. `config/settings.py`: mail settings from `.env` with console defaults, and `PASSWORD_RESET_TIMEOUT`, per the PRD. Replace the "console backend only" comment. `.env.example`: list the mail settings.
2. `accounts/forms.py`: DaisyUI-dressed subclasses of Django's password-reset and set-password forms, following `SignInForm`.
3. `accounts/views.py` and `accounts/urls.py`: the three reset views and their URLs per the PRD's table. Success URLs are namespaced; a completed reset redirects to `accounts:login` with a success message.
4. Templates in `templates/accounts/`: the request page, the "check your inbox" page, and the confirm page, which shows the form for a valid link and the expired-link state with a "request a new one" button otherwise. All extend `base.html`.
5. Plain-text email templates for the reset subject and body, per the PRD: username and link, in the store's voice. The link is built with the namespaced URL name.
6. `templates/accounts/login.html`: a "Forgot your password?" link.
7. Reset tests — PRD coverage priority 3. Expiry is tested by overriding `PASSWORD_RESET_TIMEOUT`.

**Verification.** *Automated:* reset tests green; full suite green. *Manual:* as a seeded customer, ask for a reset; copy the link from the dev-server terminal and check the email names the username; set a new password and sign in with it; open the same link again and see the expired page and its button; ask for a reset with an address that has no account and see the same "check your inbox" page with nothing printed in the terminal.

**Out of bounds:** the account page, change password, change email, checkout, real SMTP delivery.

---

## Phase 3 — The Account Page

**Goal:** A signed-in customer manages their own password and email.

**Tasks:**
1. `User.change_email` per the PRD, with the plain-text notice subject and body templates. Model tests first: the address is saved and one notice goes to the old address.
2. `EmailChangeForm` per the PRD, and a DaisyUI-dressed subclass of Django's password-change form. Form tests first — the rejections in PRD coverage priority 5.
3. Account page view, URL, and `templates/accounts/account.html` per the PRD: username, email, the change-email form, and a link to change password. A successful email change redirects back to the page with a success message.
4. Change-password view, URL, and template. Success redirects to the account page with a success message.
5. `templates/base.html`: "Hi, username" becomes a link to the account page.
6. View tests — PRD coverage priorities 4, 5, and 6.

**Verification.** *Automated:* model, form, and view tests green; full suite green. *Manual:* as a seeded customer, open the account page from the navbar; change the password, confirm the session survives, then sign out and in with the new one; change the email with a wrong password and read the error; change it correctly and read the notice to the old address in the terminal; try another seeded user's email and see it refused; signed out, request the account page and land on sign-in.

**Out of bounds:** editing the username or name, a notice on password change, email confirmation links, checkout.

---

## Phase 4 — Checkout Knows the Email

**Goal:** Checkout stops asking for an email the store already has.

**Tasks:**
1. `CheckoutView`: supply the account email as the Email field's initial value. `CheckoutForm`, `Order`, and `orders/services.py` are not changed.
2. Checkout tests — PRD coverage priority 7.

**Verification.** *Automated:* checkout tests green; the existing order and service tests untouched and green. *Manual:* as a seeded customer with a cart, open checkout and see the Email box filled; overwrite it, place the order, and confirm the order shows the overwritten address while the account page still shows the account's.

**Out of bounds:** removing the checkout Email field, any change to stored orders.

---

## Phase 5 — Documentation

**Goal:** The project's own records describe the feature.

**Tasks:**
1. `CLAUDE.md`: name this PRD and plan in the opening paragraph; in the project layout, update the `accounts/` entry to say email is required and unique ignoring case, that the app carries the account page and the password reset and change flows, and that `User.change_email` is the one place that changes an email and sends the notice.
2. `README.md`: note that reset and notice emails print in the dev-server terminal by default, and which `.env` settings switch on real mail.
3. `PROMPTS.md`: leave it alone. Its own rules say an entry is added only when the user gives the session-log prompt at the end of a session, never unprompted.
4. Final pass: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.

**Verification.** *Automated:* suite green, Ruff clean. *Manual:* from a fresh clone with no `.env`, `uv sync`, `migrate`, `seed`, and `tailwind runserver` give a store where signup asks for an email and a reset link appears in the terminal.

**Out of bounds:** anything in the PRD's Out of Scope section; committing the updated `db.sqlite3` snapshot without being asked.
