# Implementation Plan: The ThoughtTronix Store — Coupon Codes

*Companion to `prd/coupons.md`. The PRD owns the requirements; this plan owns the sequence. Where a task says "per the PRD," the PRD's wording is authoritative — do not improvise alternatives. The suite must be green at every phase boundary.*

---

## Phase 1 — The Coupon Model and the Matching Rule

**Goal:** Coupons exist and the store can pick a replacement for an expired one — proven entirely by tests, before any page shows a coupon.

**Tasks:**
1. `Coupon` model in `orders/models.py` per the PRD: fields, `DiscountType` `TextChoices`, code uppercased on save, unique code. Migration.
2. `CouponQuerySet` with `active(now=None)` and `public()`; model methods `is_expired(now=None)`, `savings_for(total)` (capped at `total`), `meets_minimum(total)`, `status(now=None)`, `__str__`.
3. Register `Coupon` in `orders/admin.py`.
4. `conftest.py`: a `coupon` fixture and a helper for building coupons with explicit `starts_at` / `expires_at`.
5. Model tests first — PRD coverage priority 1, including the exact `starts_at` and `expires_at` boundaries.
6. `find_replacement(coupon, cart, *, now=None)` in `orders/services.py` per the PRD's matching rule: chain with loop guard, closest public match in either direction, tie-breaks, `None` when nothing is found. Docstring and type hints. The per-customer check can be a stub that returns "not used up" until Phase 3 adds `Order.coupon`; write that test as `xfail` with a note.
7. `find_replacement` tests — PRD coverage priority 2, every branch.

**Verification.** *Automated:* model and matching tests green; Ruff clean. *Manual:* in the Django admin, create an expired THOUGHTS10 linked to an active THOUGHTS15; in `manage.py shell`, call `find_replacement` on a cart and get THOUGHTS15.

**Out of bounds:** cart fields, any customer-facing page, orders, back-office screens, seed.

---

## Phase 2 — Coupons on the Cart

**Goal:** Customers apply, see, and remove coupons on the cart page, and expired coupons are swapped with a notice that stays until dismissed.

**Tasks:**
1. `Cart` gains `coupon` and `coupon_notice` per the PRD; `discount()` and `grand_total()` model methods. Migration.
2. `CouponChange` dataclass, `refresh_cart_coupon(cart, *, now=None)`, and `apply_coupon(cart, code, *, now=None)` in `orders/services.py`. Notice text composed in the service from the `CouponChange`. Docstrings and type hints.
3. Service tests — PRD coverage priority 3.
4. `CouponApplyForm` (one `code` field; unknown code is a field error).
5. `CartView` and `CheckoutView` call `refresh_cart_coupon` on every load.
6. Three HTMX endpoints per the PRD — apply, remove, dismiss notice — each re-rendering `_cart_contents.html`. Existing quantity and removal endpoints re-render the coupon section too.
7. Cart partial: coupon form, applied coupon with savings, remove button, paused note ("Add $X more to use CODE"), notice as a dismissible DaisyUI alert, subtotal / discount / total.
8. Checkout order summary shows subtotal, discount, and total.

**Verification.** *Automated:* service tests; HTMX endpoints return partials; cart and checkout refresh on load; paused note shows the right shortfall. *Manual:* as `customer`, apply `fall10` (lowercase) and see the discount without a reload; remove it; apply an expired code and see the swap notice; dismiss it; lower the cart below a coupon's minimum and watch it pause, then add an item and watch it resume.

**Out of bounds:** discount on placed orders — checkout still charges full price this phase. Back office, seed.

---

## Phase 3 — Discounts on Orders

**Goal:** Placing an order honors the coupon, records it as a snapshot, and clears it from the cart.

**Tasks:**
1. `Order` gains `coupon`, `coupon_code`, and `discount` per the PRD. Migration.
2. `place_order`: refresh the cart's coupon inside the transaction; record snapshot fields only for an active, unpaused coupon; `total` after discount; clear the cart's coupon and notice with its items. The `coupon_code` parameter applies that code before refreshing. Update the docstring; remove the "seam ignored" comment.
3. Replace the per-customer stub from Phase 1 with the real `Order.coupon` count; remove the `xfail`.
4. Replace `test_the_coupon_seam_is_accepted_and_ignored` with tests for the live seam; add PRD coverage priority 4.
5. Confirmation, order history, order detail, and back-office order detail show the code and discount when present.

**Verification.** *Automated:* `place_order` tests including a coupon that expires between cart view and placement (pass two different `now` values); per-customer limit tests; full suite green. *Manual:* check out with FALL10 applied and confirm the order total and history show the discount; try to apply a once-per-customer coupon a second time and see it swapped.

**Out of bounds:** back-office coupon screens, seed.

---

## Phase 4 — The Coupons Tab

**Goal:** Staff manage coupons from the back office.

**Tasks:**
1. `CouponForm` with every rule from PRD user story 15, including the `replaced_by` loop check. Form tests first — PRD coverage priority 5.
2. List, create, update, delete views, gated by the staff mixin, following the product CRUD views' patterns; URLs and names per the PRD; `section = "coupons"`.
3. List template: code, discount, dates, status badge (scheduled / active / expired), public flag, replacement; designed empty state.
4. Add the Coupons tab to `templates/backoffice/base.html`.
5. Success messages on saves per the messages convention.

**Verification.** *Automated:* access-control tests (PRD coverage priority 6); CRUD round-trips; form rule tests. *Manual:* as `employee`, create HOLIDAY20 scheduled for Nov 25 and see it listed as scheduled; try to link a coupon to itself and see the error; link A → B → A and see the loop rejected.

**Out of bounds:** dashboard coupon analytics.

---

## Phase 5 — Seed and Polish

**Goal:** The demo world shows the feature off, and the docs match what was built.

**Tasks:**
1. Extend `seed` with the PRD's demo coupons; the `customer` demo cart holds the expired THOUGHTS10; some seeded orders use coupons. Confirm the idempotence test still passes.
2. `README.md`: a short section on demo coupon codes and what each demonstrates.
3. `CLAUDE.md`: note the coupon functions in the `orders/services.py` deep-module description; note the extended HTMX inventory.
4. Sweep: every public function in `orders/services.py` documented and typed; coupon list has its empty state; Ruff clean; CI green.

**Verification.** *Automated:* full suite green; seed runs twice with identical counts. *Manual:* fresh `seed`, sign in as `customer`, and see THOUGHTS10 already swapped for THOUGHTS20 with its notice on the cart page; check out and confirm the discount on the order.

**Out of bounds:** everything in the PRD's Out of Scope section.
