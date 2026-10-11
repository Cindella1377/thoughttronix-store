# Plan: Account Email and Passwords

> Source PRD: `prd/account-email.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: `accounts`. Checkout's one change lives in `orders`; no new app.
- **Models**: `accounts.User` redeclares `email` as a required `EmailField` with a `UniqueConstraint` on `Lower("email")`. No exemption for a blank email. One migration, no data fix. `User.change_email(new_email)` is the one place an email changes. `Order.email` stays the order's own copy.
- **URLs**: all under `/accounts/`, all named in the `accounts` namespace:

  | Name | Path | Page |
  |---|---|---|
  | `account` | `/accounts/` | Account page, including the change-email form |
  | `password_change` | `/accounts/password/change/` | Change password |
  | `password_reset` | `/accounts/password/reset/` | Ask for a reset link |
  | `password_reset_done` | `/accounts/password/reset/sent/` | "Check your inbox" |
  | `password_reset_confirm` | `/accounts/password/reset/<uidb64>/<token>/` | Choose a new password, or the expired-link page |

  No separate "done" pages for a completed reset or a changed password: each redirects with a success message.
- **Views and forms**: Django's built-in password views, subclassed in `accounts` for the app's templates, DaisyUI-dressed forms, and namespaced success URLs. Forms own their validation; views stay thin.
- **Authentication**: sign-in stays username-only. The account and change-password pages require sign-in. Customers, employees, and the admin all use the same pages.
- **Mail**: settings read from `.env` through environs and default to the store's own console backend, which prints each email as written. All messages are plain text. Reset links last one hour (`PASSWORD_RESET_TIMEOUT = 3600`). The app runs with no `.env`.
- **Testing**: sent mail is read from Django's in-memory test mailbox. Link expiry is tested by overriding `PASSWORD_RESET_TIMEOUT`, not by freezing the clock. Tests never invoke `seed`. The suite is green at every phase boundary.

---

## Phase 1: Signup collects a unique email

**User stories**: 1, 2, 19

### What to build

Every account carries an email that belongs to it alone. The user model requires an email and the database refuses a second account with the same address, whatever its capitalisation. Signup asks for the email, checks it case-insensitively, and reports a duplicate beside the Email field; the constraint is the backstop for anything that bypasses the form. After signup the visitor still lands on the sign-in page. The shared test fixtures and any users created inline in tests gain emails first, so the suite stays green across the model change. The seed keeps building the demo world, with every demo user holding a distinct email.

### Acceptance criteria

- [ ] Two accounts cannot share an email, including when only the capitalisation differs (PRD coverage priority 1)
- [ ] The migration applies to the existing database with no data fix
- [ ] Signup requires an email, rejects a duplicate with an error on the Email field, and stores the email on the new account (priority 2)
- [ ] Signup still redirects to sign-in, with no auto-login
- [ ] Every demo user's email is distinct ignoring case, read from the seed's constants without invoking the command (priority 8)
- [ ] Full suite green; Ruff clean

---

## Phase 2: Ask for a reset link

**User stories**: 3, 4, 5, 17, 18

### What to build

A customer who forgot their password can ask for help. The sign-in page links to "Forgot your password?", which leads to a page that takes an email and always redirects to the same "check your inbox" page, whether or not the address has an account. A known address is sent one plain-text email, in the store's voice, that states the username and carries the reset link. With no `.env`, that email prints whole in the dev-server terminal; filling in the mail settings in `.env` switches to real delivery with no code change, and `.env.example` lists them.

The link's destination arrives in Phase 3; this slice is demoable by reading the email in the terminal.

### Acceptance criteria

- [ ] The sign-in page links to the reset request page at `accounts:password_reset`
- [ ] A known email produces exactly one message containing the username and a reset link (priority 3, first half)
- [ ] An unknown email produces no message and the same "check your inbox" page
- [ ] The app starts with no `.env`, and the reset link prints on one line in the terminal
- [ ] Backend, host, port, username, password, TLS, and from-address are read from `.env` and listed in `.env.example`
- [ ] Full suite green

---

## Phase 3: Choose a new password from the link

**User stories**: 6, 7

### What to build

The reset link works. A valid link shows a form to choose a new password; submitting it sets the password and redirects to the sign-in page with a message that it worked. A link that is invalid, over an hour old, or already used shows a page that says so and offers a "request a new one" button back to the request page.

### Acceptance criteria

- [ ] A valid link sets the new password and redirects to `accounts:login` with a success message (priority 3)
- [ ] The customer can sign in with the new password and not the old one
- [ ] A used link shows the expired-link page with its button
- [ ] An expired link shows the same page, tested by overriding `PASSWORD_RESET_TIMEOUT`
- [ ] There is no auto-login after a reset
- [ ] Full suite green

---

## Phase 4: The account page

**User stories**: 8, 16

### What to build

A signed-in user has a page of their own. "Hi, username" in the navbar becomes a link to `/accounts/`, which shows the username and email. The page requires sign-in and is the same for customers, employees, and the admin. It does not repeat order history. The change-email form and the change-password link join it in the next two phases.

### Acceptance criteria

- [ ] The account page shows the signed-in user's username and email (priority 6)
- [ ] A signed-out request for the page redirects to sign-in
- [ ] The navbar links to the account page for signed-in users and not for visitors
- [ ] A staff user sees the same link and the same page
- [ ] Full suite green

---

## Phase 5: Change password

**User stories**: 9, 10, 16

### What to build

From the account page, a signed-in user follows a link to change their password by entering the current one and a new one twice. Success returns them to the account page with a success message, still signed in on this device and signed out on their others.

### Acceptance criteria

- [ ] The account page links to `accounts:password_change`
- [ ] The change-password page requires sign-in (priority 4)
- [ ] A wrong current password is rejected and the password is unchanged
- [ ] A valid change sets the new password, keeps the current session, and redirects to the account page with a success message
- [ ] No notice email is sent for a password change
- [ ] Full suite green

---

## Phase 6: Change email

**User stories**: 11, 12, 13, 16

### What to build

The account page gains a form that takes a new email and the current password. It refuses a wrong password, an address held by another account (ignoring case), and the address the account already has. A valid change goes through `User.change_email`, which saves the new address and sends a plain-text notice to the old one saying the email was changed and to contact the store if that was unexpected, without naming the new address. The user returns to the account page with a success message.

### Acceptance criteria

- [ ] `User.change_email` saves the new address and sends exactly one notice, to the old address
- [ ] The notice does not include the new address
- [ ] A wrong password, another account's address in any capitalisation, and an unchanged address are each rejected with nothing saved or sent (priority 5)
- [ ] A valid change redirects to the account page, which shows the new email and a success message
- [ ] Posting the form while signed out redirects to sign-in
- [ ] Full suite green

---

## Phase 7: Checkout knows the email

**User stories**: 14, 15

### What to build

Checkout stops asking for an email the store already has. The checkout form's Email box starts filled with the account's email and can be overwritten for that order. The checkout form, the order's own email field, and `place_order` do not change, so an order keeps the address it was placed with even if the account's email changes later.

### Acceptance criteria

- [ ] The checkout Email field is prefilled with the account email (priority 7)
- [ ] An order placed with an overwritten address stores the overwritten one, and the account's email is unchanged
- [ ] Changing the account email afterwards does not alter the email on orders already placed
- [ ] Existing order and service tests pass untouched
- [ ] Full suite green; Ruff clean
