# PRD: The ThoughtTronix Store — Coupon Codes

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

*Builds on `prd/core-platform.md`. Where this document is silent, the core PRD's conventions hold.*

---

## Problem Statement

Marketing has printed forty thousand flyers reading "THOUGHTS10 — 10% off your first MindSync." The store cannot accept it. `place_order` has carried a `coupon_code` parameter since the core build, and it has ignored every code it was handed.

Worse, marketing's promotions expire. A customer who applies a code on Monday and returns on Friday should not be met with an error, a silently vanished discount, or a total that changed without explanation. Our customers have enough on their minds; most of it, admittedly, is ours.

We need coupon codes that staff can schedule, customers can apply, and that — when they expire — are replaced automatically with the closest available offer, with a clear explanation the customer cannot miss.

## Solution

**Coupons.** Staff create coupons in a new back-office tab. A coupon gives either a percentage or a fixed amount off, runs between a start and an end date, and may carry a minimum order and a once-per-customer limit. Staff can link a coupon to the coupon that replaces it, and can mark coupons as public — eligible to be offered automatically.

**The cart.** Customers enter a code on the cart page. The applied coupon lives on the cart, so the discount is visible while they shop and survives across visits.

**The swap.** Whenever the cart is viewed, a code is entered, or an order is placed, an expired coupon is swapped for a live one: first by following the staff-set replacement chain, then by choosing the public coupon whose savings on this cart are closest to what the expired coupon would have saved. If nothing is available, the coupon is removed. Either way, the cart shows a notice explaining exactly what changed and why, until the customer dismisses it. The customer never sees an error.

## User Stories

**Customer**

1. As a customer, I can enter a coupon code on my cart page and see the discount and the discounted total without a full page reload. A cart holds one coupon at a time; entering a new code replaces the current one.
2. As a customer, codes are not case-sensitive — `thoughts10` works.
3. As a customer, I can remove an applied coupon from my cart.
4. As a customer, if my coupon expires while it sits in my cart, it is replaced with the closest available coupon the next time I view my cart, and a notice tells me which code expired and which one replaced it.
5. As a customer, if no replacement exists, the expired coupon is removed and a notice tells me so. I never see an error.
6. As a customer, if I type in a code that has already expired, it goes through the same swap as an expired coupon in my cart.
7. As a customer, the swap notice stays on my cart until I dismiss it or place my order, so I always understand why my discount changed.
8. As a customer, if my cart drops below a coupon's minimum order, the coupon stays on my cart, paused, with a note telling me how much more to add. The discount returns automatically when my cart reaches the minimum.
9. As a customer, a coupon can never make my total negative.
10. As a customer, my coupon is re-checked when I place my order, so the discount I am charged is the discount the store honors.
11. As a customer, my order confirmation, order history, and order detail show the coupon code I used and the amount it saved me.

**Employee (staff)**

12. As an employee, I can view a list of all coupons in a Coupons tab of the back office, showing each one as scheduled, active, or expired — with a designed empty state before any coupons exist.
13. As an employee, I can create, edit, and delete coupons: code, discount type (percent or fixed amount), value, start date, end date, optional minimum order, optional once-per-customer limit, public flag, and optional replacement coupon.
14. As an employee, I can schedule a coupon ahead of time; it switches on and off by itself at its start and end dates, with no background job.
15. As an employee, the coupon form rejects invalid input: a percentage outside 1–100, a non-positive value, an end date before the start date, a duplicate code (case-insensitive), and a replacement link that points to itself or forms a loop.
16. As an employee, I can see which coupon an order used on the back-office order detail page.

**Any developer**

17. As a developer, the seed command creates demo coupons — including an expired coupon with a replacement chain and several public coupons — so the swap can be demonstrated immediately.

## Implementation Decisions

**The `Coupon` model** (in `orders`). Fields: `code` (unique, stored uppercase), `discount_type` (`TextChoices`: `PERCENT`, `AMOUNT`), `value` (`DecimalField`), `starts_at`, `expires_at`, `minimum_order` (nullable `DecimalField`), `once_per_customer` (boolean), `is_public` (boolean), `replaced_by` (nullable self-FK, `on_delete=SET_NULL`), `created_at`.

- A coupon is **active** when `starts_at <= now < expires_at`. It counts as expired *at* `expires_at`, not a second later. Expiry is always computed, never stored — no `is_active` flag, no scheduled job.
- Custom queryset: `Coupon.objects.active(now=None)` and `.public()`. `now` defaults to `timezone.now()`.
- Model methods: `is_expired(now=None)`, `savings_for(total)` — percent or fixed amount, **capped at `total`**, never negative — and `meets_minimum(total)`.
- `status(now=None)` returns scheduled / active / expired, for the back-office list.

**The cart.** `Cart` gains `coupon` (nullable FK to `Coupon`, `SET_NULL`) and `coupon_notice` (blank `TextField`). New methods: `discount()` — the coupon's savings on the cart total, or zero if no coupon is applied or its minimum is not met (the *paused* state) — and `grand_total()`, which is `total() - discount()`. Pricing methods assume the coupon has been refreshed; they never swap.

**The swap workflow, in `orders/services.py`.** The swap spans `Cart`, `Coupon`, and past `Order`s — a cross-model workflow — so it lives in the existing deep module, beside `place_order`, which was built with coupons in mind. This keeps the codebase at exactly two deep modules. Public functions, each with a docstring and type hints:

- `refresh_cart_coupon(cart, *, now=None) -> CouponChange | None` — if the cart's coupon is expired or used up by this customer, replace it and write the notice. Returns what changed, or `None` if nothing did.
- `apply_coupon(cart, code, *, now=None) -> CouponChange` — look up the code (case-insensitive) and attach it, running the same swap if the code has expired or been used up. An unknown code is a form error, not a swap.
- `find_replacement(coupon, cart, *, now=None) -> Coupon | None` — the matching rule, exposed on its own so it can be tested directly.

`CouponChange` is a small dataclass recording the old coupon, the new coupon (or `None`), and the reason. The service writes `cart.coupon_notice` from it; views never compose notice text.

**The matching rule** (`find_replacement`), in order:

1. **Follow the chain.** Walk `replaced_by` links to the first coupon that is active and not used up by this customer. Keep a set of visited coupons; stop if one repeats (loop guard). A chain target whose minimum the cart does not meet is still applied — staff chose it — and simply starts out paused.
2. **Closest public match.** If the chain yields nothing, consider every active, public coupon that the cart meets the minimum for and that the customer has not used up. Compute what each would save on this cart. Pick the one whose savings are **closest, in either direction**, to what the expired coupon would have saved.
3. **Tie-break.** Equal distance → the bigger saving wins. Equal savings → the most recently created coupon wins. The result is deterministic.
4. **Nothing found.** Return `None`; the caller removes the coupon.

**Notices.** The cart stores the most recent notice in plain language — for example: *"THOUGHTS10 expired on Sep 30. We applied FALL10 instead, which saves you $7.50 on this cart."* or *"THOUGHTS10 expired on Sep 30, and no replacement is available right now."* The cart page shows it in a DaisyUI alert with a dismiss button. A new notice replaces the old one. The cart also remembers the swapped-out coupon (`replaced_coupon`) and why (`replaced_coupon_status`: "Expired", "Already used", or "Not running"), and the coupon line shows it faded and struck through beside its replacement — `~~SUMMER5~~ Expired → SAVE15` — so the customer can see their code was replaced, not lost. Dismissing the notice keeps the faded code; applying another code, removing the coupon, or placing the order clears it. The paused-coupon note ("Add $10.00 more to use SAVE10") is not stored — it is computed on display.

**Per-customer limit.** A coupon with `once_per_customer` is used up for a customer once they have any order linked to it. Counted with a single query over `Order.coupon`.

**Orders.** `Order` gains `coupon` (nullable FK, `SET_NULL`), `coupon_code` (blank `CharField`, snapshot), and `discount` (`DecimalField`, default `0`). `total` stores the amount **after** discount. `place_order` refreshes the cart's coupon inside its transaction before pricing, records the snapshot fields only if the coupon is active and not paused, and clears `cart.coupon` and `cart.coupon_notice` along with the cart's items. The dormant `coupon_code` parameter becomes live: if passed, `place_order` applies that code to the cart before refreshing. The checkout view does not pass it; the cart page is the one entry point for codes.

**Customer UI.** The cart page gets a coupon form, the applied coupon with its savings, a remove button, the paused-coupon note, and the notice alert. The cart and checkout views call `refresh_cart_coupon` on every load. Checkout's order summary shows subtotal, discount, and total. Confirmation, order history, and order detail show the code and discount when present.

**HTMX.** This feature extends the core PRD's three-interaction HTMX inventory with three more, all on the cart page and all swapping `templates/orders/partials/_cart_contents.html` (totals change with each): apply coupon, remove coupon, dismiss notice. Existing quantity and removal swaps now also re-render the coupon section, since a changed total can pause or resume a coupon. Coupon feedback travels inside the partial — no flash messages for coupon actions, per the core messages convention.

**Back office.** A new **Coupons** tab in `templates/backoffice/base.html` (`section == "coupons"`). List, create, update, delete views gated by the existing staff mixin, following the product CRUD views' patterns, pk URLs, and the naming scheme `orders:manage_coupons`, `orders:manage_coupon_create`, `orders:manage_coupon_update`, `orders:manage_coupon_delete`. The list shows code, discount, dates, status, public flag, and replacement, with a designed empty state. `CouponForm` owns all validation from user story 15; the loop check walks the proposed `replaced_by` chain. Success messages on saves per the messages convention. `Coupon` is also registered in the Django admin for debugging.

**URLs (customer).** `orders:apply_coupon` (`cart/coupon/`), `orders:remove_coupon` (`cart/coupon/remove/`), `orders:dismiss_coupon_notice` (`cart/coupon/notice/dismiss/`). POST only.

**Seed data.** The seed command creates: an expired `THOUGHTS10` (10% off) replaced by an expired `THOUGHTS15`, replaced by an active `THOUGHTS20`; an expired, unlinked `SUMMER5` ($5 off) to demonstrate closest-match; active public coupons `FALL10` (10%), `SAVE15` ($15 off, $75 minimum), and `WELCOME5` ($5, once per customer); a scheduled `HOLIDAY20` starting Nov 25; and a non-public `STAFFONLY50`. The `customer` demo login's live cart holds the expired `THOUGHTS10`, so the swap notice appears on first sign-in. Some seeded orders use coupons, so order history and the dashboard show discounts.

## Testing Decisions

Same stack and fixture style as the core: pytest + pytest-django, plain fixtures in `conftest.py` (a `coupon` fixture and a factory-free helper for building coupons with explicit dates). Tests never invoke the seed command.

**Time control.** Every time-dependent function takes an optional `now`. Tests pass exact datetimes — no `time-machine`, no `freezegun`. Tests that do not care about exact moments may use relative dates, like the rest of the suite.

Coverage priorities, in order:

1. **`Coupon` model** — `savings_for` for percent and amount, capped at the cart total; `active()` at exactly `starts_at` (active) and exactly `expires_at` (expired); `meets_minimum`; `status`.
2. **`find_replacement`** — chain followed to the first active coupon; chain through a used-up coupon skips it; loop guard terminates; chain target below minimum is still returned; closest match in either direction; non-public coupons never matched; below-minimum and used-up coupons excluded from matching; tie → bigger saving; identical saving → newest; nothing found → `None`.
3. **`refresh_cart_coupon` and `apply_coupon`** — swap writes the notice and returns the change; removal writes the notice; active coupon is untouched; typed expired code swaps; unknown code raises the form-level error; codes match case-insensitively.
4. **`place_order`** — discount and snapshot fields recorded; `total` is after discount; a coupon that expires between cart view and checkout is swapped at placement; a paused coupon records no discount; cart coupon and notice cleared; the old "seam ignored" test is replaced.
5. **`CouponForm`** — each rule from user story 15 rejects bad input with a field-specific error, including self-link and multi-step loops.
6. **Access control** — coupon back-office URLs return 302/403 for anonymous users and customers.
7. **Views** — cart and checkout call the refresh; the three HTMX endpoints return the partial; the notice renders and dismisses; the paused note shows the right shortfall.

## Out of Scope

- Total (store-wide) usage limits, which require row locking.
- Stacking more than one coupon on a cart.
- Coupons restricted to specific products or categories.
- A scheduled job or task queue; emailing staff when a coupon expires.
- A coupon field on the checkout page.
- Coupon usage analytics on the dashboard (the `Order.coupon` link makes this a small future addition to `dashboard/queries.py`).
