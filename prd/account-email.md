# PRD: The ThoughtTronix Store — Account Email and Passwords

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

*Builds on `prd/core-platform.md`. Where this document is silent, the core PRD's conventions hold.*

---

## Problem Statement

A customer who forgets their password is locked out for good. Signup asks for a username and a password and nothing else, so the store has no way to reach the person behind an account, and no way to prove that someone asking for a new password is that person. There is also no page where a signed-in customer can change a password they still remember. The only fix for either is a staff member editing the account by hand in the admin site, which does not scale past a handful of customers.

We need every account to carry an email address that belongs to it alone, a way to reset a forgotten password through that address, and a place where customers manage their own password and email without involving staff.

## Solution

**An email on every account.** Signup asks for an email address and refuses one that another account already uses.

**Forgotten password.** The sign-in page links to "Forgot your password?". The customer enters their email and is sent a link that lets them choose a new password. The email also states their username. The link works for one hour and only once.

**An account page.** "Hi, username" in the navbar becomes a link to the customer's account page, which shows their username and email, lets them change the email, and links to a change-password page.

**Changing the password.** A signed-in customer enters their current password and a new one.

**Changing the email.** A signed-in customer enters the new address and their current password. The old address is sent a notice that the email was changed.

**Checkout.** The checkout form's Email box starts filled with the account's email and can still be edited for that order.

## User Stories

**Visitor**

1. As a visitor, I must give an email address to create an account.
2. As a visitor, signup refuses an email that another account already uses, whatever its capitalisation, and tells me so beside the Email field.

**Customer**

3. As a customer who forgot my password, I can ask for a reset link from the sign-in page by entering my email.
4. As a customer, the reset email tells me my username, so I can get back in even if I forgot both.
5. As a customer, the page I see after asking for a reset is the same whether or not the address has an account, so nobody can use it to find out who shops here.
6. As a customer, the reset link lets me choose a new password, then sends me to the sign-in page with a message that it worked.
7. As a customer, a reset link that is over an hour old or already used shows me a page that says so and offers a button to request a new one.
8. As a customer, I can reach my account page from the navbar and see my username and email there.
9. As a customer, I can change my password by entering my current password and a new one twice.
10. As a customer, changing my password signs me out on my other devices and keeps me signed in on this one.
11. As a customer, I can change my email by entering the new address and my current password.
12. As a customer, changing my email is refused when the new address belongs to another account, when my current password is wrong, or when the address is the one I already have.
13. As a customer, my old address is sent a notice when my email changes, so I find out if it was not me.
14. As a customer, the checkout Email box is already filled with my account email, and I can overwrite it for one order.
15. As a customer, changing my account email later does not alter the email recorded on orders I already placed.

**Employee (staff) and admin**

16. As an employee or admin, I use the same reset, change-password, and account pages as customers.

**Any developer**

17. As a developer, the app still runs with no `.env`: reset and notice emails are printed in the dev-server terminal.
18. As a developer, I can send real mail by filling in the mail settings in `.env`, with no code change.
19. As a developer, `seed` still builds the demo world, with every demo user holding a distinct email.

## Implementation Decisions

**The email rule.** `accounts.User` redeclares `email` as a required `EmailField`, and gains a database constraint that no two accounts share an email, compared case-insensitively (a `UniqueConstraint` on `Lower("email")`). There is no exemption for a blank email: a blank is a value like any other, so at most one account could ever hold it, and all code that creates users supplies an email. One migration. The twelve existing users already have distinct, non-blank emails, so the migration needs no data fix.

**Signup.** `SignupForm` gains `email`. Its `clean_email` checks for an existing account with a case-insensitive match and puts the error on the Email field. The database constraint is the backstop for anything that bypasses the form. After signup the customer is still sent to the sign-in page, as today.

**Mail settings.** The mail settings read from `.env` through environs, defaulting to the console backend: backend, host, port, username, password, TLS, and the from-address. `.env.example` lists them. The default is the store's own console backend, a small subclass of Django's that prints each email as written: Django's prints the encoded message, which splits a reset link across two lines. Reset links last one hour (`PASSWORD_RESET_TIMEOUT = 3600`).

**Views.** Django's built-in password views, subclassed in `accounts` so they use the app's templates, forms dressed in DaisyUI classes, and namespaced success URLs. Sign-in stays username-only.

**URLs.** All under `/accounts/`, all named in the `accounts` namespace:

| Name | Path | Page |
|---|---|---|
| `account` | `/accounts/` | Account page, including the change-email form |
| `password_change` | `/accounts/password/change/` | Change password |
| `password_reset` | `/accounts/password/reset/` | Ask for a reset link |
| `password_reset_done` | `/accounts/password/reset/sent/` | "Check your inbox" |
| `password_reset_confirm` | `/accounts/password/reset/<uidb64>/<token>/` | Choose a new password, or the expired-link page |

There are no separate "done" pages for a completed reset or a changed password: a completed reset redirects to sign-in, and a changed password or email redirects to the account page, each with a success message.

**Password reset.** The request page always redirects to the same "check your inbox" page. The reset email is plain text, written in the store's voice, and contains the username and the link. The confirm page shows the new-password form for a valid link and the expired-link page, with a "request a new one" button, for an invalid, expired, or used one.

**The account page.** Requires sign-in. Shows username and email, the change-email form, and a link to change password. It does not repeat order history; the navbar already links to it.

**Changing the email.** `EmailChangeForm` takes the new email and the current password. It rejects a wrong password, an address held by another account (case-insensitive), and the address the account already has. The change itself is a model method, `User.change_email(new_email)`, which saves the new address and sends the notice to the old one; the form calls it and the view stays thin. The notice is plain text and says the email on the account was changed and to contact the store if that was unexpected. It does not include the new address.

**Navbar.** "Hi, username" becomes a link to the account page for every signed-in user.

**Checkout.** `CheckoutView` supplies the account email as the Email field's initial value. `CheckoutForm`, `Order.email`, and `place_order` are unchanged: the order still stores its own copy.

**Seed.** The demo users already carry distinct emails. No seed behaviour changes.

## Testing Decisions

Tests read sent mail from Django's in-memory test mailbox. Time-dependent behaviour is the reset link's expiry, which is tested by overriding `PASSWORD_RESET_TIMEOUT` rather than freezing the clock. The shared user fixtures in `conftest.py`, and the handful of tests that create users inline, gain emails.

Coverage, in priority order:

1. The email rule: two accounts cannot share an email, including when only the capitalisation differs.
2. `SignupForm`: requires an email, rejects a duplicate with a field error, creates the account with the email stored.
3. Password reset: a known email produces one message containing the username and a working link; an unknown email produces none and the same page; the link sets a new password and redirects to sign-in; a used link and an expired link show the expired page.
4. Change password: requires sign-in, rejects a wrong current password, changes the password and keeps the session.
5. Change email: requires sign-in; rejects a wrong password, another account's address, and an unchanged address; on success stores the new address and sends one notice to the old address.
6. Account page and navbar: the page shows username and email; the navbar links to it for signed-in users only.
7. Checkout: the Email field is prefilled from the account, and an order placed with an overwritten address stores the overwritten one.
8. Seed data: every demo user's email is distinct ignoring case, read from the seed's constants without invoking the command.

## Out of Scope

- Confirming an email address by a link, at signup or when it is changed. A mistyped address is the customer's to correct on the account page.
- Signing in with an email address.
- A notice email when a password is changed or reset.
- Limiting how often reset links can be requested.
- A separate "forgot my username" page. The reset email states the username.
- HTML email. Messages are plain text.
- Editing the username, name, or anything else on the account page.
- Auto-login after signup or after a reset.
- Choosing a real mail provider. The settings exist; production delivery is not set up or tested.

## Further Notes

- Signup tells a visitor when an email is already registered, while the reset page does not. That difference is accepted: signup cannot refuse a duplicate without saying why.
- The repository tracks a `db.sqlite3` snapshot for grading. Applying this feature's migration changes that file; whether to commit the updated snapshot is a separate decision.
