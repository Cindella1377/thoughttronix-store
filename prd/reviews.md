# PRD: The ThoughtTronix Store — Product Reviews

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

*Builds on `prd/core-platform.md`, `prd/product-images.md`, and `prd/wishlists.md`. Where this document is silent, the core PRD's conventions hold.*

---

## Problem Statement

A shopper deciding whether to buy has only the store's own word to go on. Every product page carries a tagline and a description written by ThoughtTronix, and nothing written by anyone who has actually owned the product. There is no way for a customer who received a Seraphine to say how it went, and no way for the next shopper to compare products by how they were received.

The store also has no way to show that an opinion is earned. Any review system that lets anyone post invites ratings from people who never bought the product, or who bought it and sent it back. A review is only worth reading if the reader can trust that the writer had the product in hand.

## Solution

**Galaxies, not stars.** Customers rate a product from one to five galaxies, and each level has a name: 1 *Black hole* ("it took something from me"), 2 *Space junk*, 3 *Low orbit*, 4 *Stellar*, 5 *Out of this world*.

**Confirmed buyers only.** Only a customer with a Delivered order containing the product can review it, and only once. The review belongs to the account that placed the order; anyone else who has the product in hand, a SoulSear owner's next of kin included, cannot review it. A purchase that is sent back stops counting: if an order stops being Delivered and the customer has no other Delivered order for that product, their review is removed.

**What a review holds.** A galaxy rating (required), written text (optional), and one photo (optional).

**On the product page.** A reviews section under the product shows the galaxy average and review count, the form or a message saying why there is no form, and the reviews themselves, newest first, ten at a time. Writing, editing, deleting, and loading more reviews all happen without the page reloading, and each action changes only the part of the page it touches, so the customer never loses their place.

**Every card is honest about itself.** Each review shows the reviewer's first name, a "Confirmed buyer · bought <month year>" badge, the date it was posted, and whether it has been edited, and by whom: the reviewer, or ThoughtTronix staff.

**On the catalog.** Each product card shows its galaxy average and review count once it has reviews.

**For staff.** Staff edit and delete any review in place on the product page, with the same controls customers use on their own. A new back-office Reviews tab lists every review, newest first, each linking to the review on its product page.

## User Stories

**Visitor**

1. As a visitor, I can read every product's reviews, its galaxy average, and its review count without an account.
2. As a visitor, I see the galaxy average and review count on each catalog card for a product that has reviews, and nothing for one that has none.
3. As a visitor, the form's place on a product page tells me to sign in to review a product I've received, and signing in brings me back to that product's reviews.
4. As a visitor, a product with no reviews shows a designed empty state, not a blank section.
5. As a visitor, I can tap "Show more reviews" to add the next ten below the ones I'm reading, without the page reloading or jumping.

**Customer**

6. As a customer with a Delivered order containing a product, I can review it by choosing one to five galaxies, optionally writing text, and optionally adding one photo.
7. As a customer, the galaxy picker shows each level's name as I choose.
8. As a customer, submitting my review replaces the form with my new review card, and the average and count update, without the page reloading.
9. As a customer, I am told, inside the form and without losing what I typed, when I have not chosen a rating, my text is over 2,000 characters, or my photo is over 2 MB.
10. As a customer, I can review a product once; after that the form's place offers "Edit your review".
11. As a customer, my own review is pinned at the top of the list, above everyone else's.
12. As a customer, I can edit my review in place: the card becomes a form, and saving or cancelling turns it back into a card, without the page reloading.
13. As a customer, when editing I can keep, replace, or remove my photo.
14. As a customer, my edited review says "edited" with the date.
15. As a customer, I can delete my review: the card asks "Delete this review? Yes, delete · Keep it", and confirming removes it in place, without the page reloading.
16. As a customer whose order for a product is Placed or Shipped, I am told my order is on its way and I can review the product once it is delivered.
17. As a customer who has never received a product, I am told reviews come from customers who have received it.
18. As a customer, if a purchase is cancelled after delivery and I have no other Delivered order for that product, my review of it, and its photo, are removed.
19. As a customer, my review shows my first name, falling back to my username, and never my email.
20. As a customer, I can review a product the store no longer sells, under the same rules as any other.
21. As a customer, I cannot edit or delete another customer's review.

**Employee (staff) and admin**

22. As an employee or admin, I see Edit and Delete on every review on a product page, and they work in place exactly as they do for a review's author.
23. As an employee or admin, a review I edit says "edited by ThoughtTronix staff"; if its author edits it afterwards, it goes back to "edited".
24. As an employee or admin, I can write a review only if I have my own Delivered order for the product; otherwise the form's place shows nothing.
25. As an employee or admin, the back-office Reviews tab lists every review, newest first, with its product, galaxies, author, date, and the start of its text, and each row opens the review on its product page.
26. As an employee or admin, the Reviews tab shows a designed empty state when there are no reviews.
27. As an employee or admin, changing an order's status away from Delivered removes the reviews it no longer supports.

**Any developer**

28. As a developer, `seed` creates sample reviews that each obey the confirmed-buyer rule, cover all five galaxy levels, give one product more than ten reviews, include one staff-edited review, and include a 1-galaxy review of the SoulSear Mark I from a customer who bought it before the recall.
29. As a developer, the demo `customer` starts with no reviews, so they can write one.

## Implementation Decisions

**A new app.** `reviews` owns the model, views, templates, and URLs. It touches other apps only at their edges: the product page and catalog cards include its partials, the back-office rail gains a Reviews tab, the order-status view calls its clean-up rule, and `seed` creates sample reviews.

**Model.**

- `Review`: product (cascade), author (foreign key to the user, cascade), `rating`, `body` (optional, up to 2,000 characters), `image` (optional, uploaded to `reviews/`), `created_at`, `updated_at`, and `edited_by_staff`.
  - A `UniqueConstraint` on product and author enforces one review per customer per product.
  - `Review.Rating` is an `IntegerChoices` holding the five galaxy names, the one place that maps a number to its name. The labels are 1 "Black hole", 2 "Space junk", 3 "Low orbit", 4 "Stellar", 5 "Out of this world". *Black hole* also carries its tagline, "it took something from me".
  - `updated_at` is null until the first edit, so a review that was never edited shows no marker.
  - Ordered newest first.

**The rules live on the model's manager.** Logic stays in models and managers, per the architecture convention. No service module is added; `CLAUDE.md` names exactly two, and nothing here reaches across models on the scale of `place_order`.

- `Review.objects.eligibility(user, product)` returns one status the template switches on: `signed_out`, `can_review`, `has_reviewed`, `on_its_way` (only Placed or Shipped orders for the product), `staff` (staff with no Delivered order), or `not_a_buyer` (never ordered it, or only Cancelled orders). A staff member with their own Delivered order gets `can_review` or `has_reviewed` like anyone else.
- Being a confirmed buyer means having an order with status Delivered whose items include the product. `OrderItem.product` is a nullable foreign key, so a line whose product was deleted counts for nothing, and so does the product it pointed at, which is gone along with its reviews.
- `Review.objects.remove_unqualified(order)` deletes every review by the order's customer, for the products on that order, where the customer no longer has any Delivered order containing that product. It returns how many it removed. Reviews are deleted one by one, not through a queryset delete, so each photo file is deleted with its review.
- `Review.can_edit(user)`: true for the author and for any staff user. Edit and delete views check it and 404 otherwise, the same as wishlists do for lists that are not yours.
- Saving an edit sets `updated_at` and sets `edited_by_staff` to whether the editor is not the author.

**The clean-up hook.** `UpdateOrderStatusView` in `orders/views.py` calls `Review.objects.remove_unqualified(order)` after saving a new status. It is an explicit call, not a Django signal, so the rule is easy to find and to test. It only removes reviews; moving an order back to Delivered unlocks the form again but does not restore the old review. The customer is not notified. Any move away from Delivered counts, including a staff slip such as Delivered → Shipped. The store has no Returned status; a return is recorded as Cancelled.

**The form.** `ReviewForm` is a `ModelForm` over `rating`, `body`, and `image`. The rating is five radio buttons styled as galaxies (DaisyUI's `rating` component), so it works by keyboard and screen reader with no JavaScript. The photo uses Django's clearable file input, so an edit can keep, replace, or remove it. The 2 MB limit reuses the product form's rule and message from `products/forms.py`, moved somewhere both forms can import rather than copied. The form posts with `hx-encoding="multipart/form-data"`, without which HTMX sends only the photo's file name.

**The galaxy icon.** One inline SVG galaxy in `templates/reviews/partials/_galaxies.html`, drawn five times, filled or faded with DaisyUI classes. The same partial shows a review's rating and, given an average, a product's (for example "4.3 galaxies (12)"). It has an `aria-label` such as "4 out of 5 galaxies, Stellar". No emoji: they render differently on every device.

**The product page.** `templates/reviews/partials/_section.html` holds the reviews section and is included by `templates/products/detail.html`. It contains:

- `_summary.html`: the galaxy average and count, or "No reviews yet" when there are none.
- The form's place, switching on `eligibility`:
  - `signed_out`: "**Sign in** to review a product you've received", linking to sign-in with `next` set to the product page's `#reviews` anchor.
  - `can_review`: the review form.
  - `has_reviewed`: nothing more; the author's own card at the top of the list carries Edit and Delete.
  - `on_its_way`: "Your order's on its way. You can review it once it's delivered."
  - `not_a_buyer`: "Reviews come from customers who've received this product." This covers returns too, so the page never reminds anyone of a return.
  - `staff`: nothing.
- The list: the viewer's own review first if they have one, then everyone else's, newest first, ten per page. Each review is `_card.html`, anchored `#review-<pk>`.
- A "Show more reviews" button, shown while more remain, that fetches the next ten and adds them below the last card. The button's response carries the next button, or none at the end.

**Cards.** Each card shows the galaxies and level name, the reviewer's first name (falling back to the username), "Confirmed buyer · bought <Mon YYYY>", "Posted <date>", the edit marker ("edited <date>" or "edited by ThoughtTronix staff <date>"), the text, and the photo as a thumbnail that links to the full-size image. Edit and Delete show only when `can_edit` is true for the viewer.

**The bought date.** The badge uses the month of the author's most recent Delivered order containing the product. The store records when an order was placed, not when it was delivered, so the badge says "bought", which is accurate. The date is fetched in the list query as a subquery annotation, never per card. Showing only the month keeps the reviewer's order history private.

**The no-reload interactions.** Each is an HTMX request that swaps only what it changes. Every write response also updates `_summary.html` with an out-of-band swap, so the average and count always match the list.

| Action | Swaps |
|---|---|
| Submit a new review | The form's place becomes the new card |
| Edit | The card becomes `_form.html` in place |
| Save or cancel an edit | The form becomes the card again |
| Delete | The card's buttons become `_confirm_delete.html`: "Delete this review? Yes, delete · Keep it" |
| Yes, delete | The card is removed, and the form's place is re-rendered (the author can now review again) |
| Keep it | The buttons come back |
| Show more reviews | The next ten cards and the next button are added below |

A form that fails validation is returned with its errors and with everything the customer entered, in the same place. Delete uses an inline confirm and not `hx-confirm`: the browser's dialog cannot be styled with DaisyUI and blocks the browser-automation tools.

**Catalog ratings.** `Product.objects.with_rating()` annotates each product with its average rating and review count in one query. The catalog and category views use it, and each card includes `_galaxies.html` when the count is above zero. The product page uses the same annotation for its summary.

**Unavailable products.** No special case. A product the store no longer sells keeps its reviews section, and Delivered buyers may still review it. No one can order an unavailable product, so no one can become a new buyer of it.

**Moderation.** Reviews are live the moment they are posted. There is no approval queue and no report button. The confirmed-buyer rule already stops anyone without a Delivered order from posting, and staff can edit or delete any review.

**Back-office Reviews tab.** `templates/reviews/manage_reviews.html` extends `templates/backoffice/base.html` with `section` set to `reviews`, and the tab rail gains a Reviews tab. It is a list only, newest first, paginated, with a designed empty state. Each row shows the product, the galaxies, the author, the posted date, the first part of the text, and the edit marker, and links to `<product url>#review-<pk>`. There are no edit or delete screens here; those live on the product page.

**Seed.** The seed writes fixed sample reviews, about 15 to 25, in the store's voice, from a constant so tests can read them without invoking the command. Each sample names a background customer and a product that customer has a Delivered order for, and the seed checks this, so it can never make a review the app itself would refuse. Across the samples:

- every galaxy level appears;
- one product has more than ten reviews, so "Show more reviews" appears;
- one review has `edited_by_staff` set;
- the demo `customer` writes none, but their existing orders already show the form (MindSync, SyncRest, DreamWeaver, all Delivered) and the "on its way" message (Seraphine Mini and Wall Mount, Shipped; Veil, Placed).

The background orders never include Defense products, so the seed adds one more order: a background customer's Delivered SoulSear Mark I order dated before the 2024 recall, with a 1-galaxy *Black hole* review. It is far older than the 182 days the background orders span, so it stays out of the dashboard's default 30-day view.

**URLs.** All named in the `reviews` namespace. Writes use pks, like the back office:

| Name | Path | Page |
|---|---|---|
| `create` | `/reviews/new/<product_pk>/` | Submit a review (POST, HTMX) |
| `more` | `/reviews/product/<product_pk>/?page=<n>` | The next ten cards (GET, HTMX) |
| `edit` | `/reviews/<pk>/edit/` | The edit form (GET) or save it (POST, HTMX) |
| `card` | `/reviews/<pk>/` | One card, for Cancel and Keep it (GET, HTMX) |
| `confirm_delete` | `/reviews/<pk>/delete/` | The inline confirm (GET) or delete (POST, HTMX) |
| `manage` | `/manage/reviews/` | The back-office Reviews tab |

**Every list view has a designed empty state:** a product with no reviews, and the Reviews tab with none.

## Testing Decisions

Tests use the shared fixtures in `conftest.py` (`customer`, `staff_user`, `product`, `unavailable_product`, `photo`) and the autouse `media_root` fixture, so uploaded photos never touch the real `media/`. A small fixture for a Delivered order of `product` by `customer` is added there. Tests never invoke the seed command. Nothing here depends on the clock, so no `now` argument is needed.

Coverage, in priority order:

1. Eligibility: each of the six statuses from the order histories that produce it, including a staff user with and without their own Delivered order, a Cancelled-only history giving `not_a_buyer`, and a Placed or Shipped history giving `on_its_way`.
2. Creating: a Delivered buyer can post; anyone else's POST is refused with no review made; a second review of the same product is refused by the form and by the database constraint.
3. Clean-up: moving the only Delivered order to Cancelled (and to Shipped) removes the review and deletes its photo file; a second Delivered order for the same product keeps it; reviews of other products are untouched; moving back to Delivered does not restore it.
4. Permissions: the author and staff can edit and delete; another customer and a visitor get a 404 and nothing changes.
5. Edit marker: an author's edit sets `updated_at` and leaves `edited_by_staff` false; a staff edit sets it true; a later author edit sets it false again; an unedited review shows no marker.
6. Validation: a missing rating, text over 2,000 characters, and a photo over 2 MB each return the form with its error and the entered values; text may be blank.
7. Photo: a review can be posted with a photo; an edit can keep, replace, or clear it, and replacing or clearing deletes the old file.
8. HTMX responses: each action returns the partial from the table above, without `base.html`, and each write response carries the out-of-band summary with the right average and count.
9. Listing: newest first, ten per page, the viewer's own review first and not repeated further down, "Show more" absent on the last page; cards show the first name, falling back to the username, and never the email; the bought badge shows the month of the most recent Delivered order.
10. Catalog: `with_rating()` gives the right average and count; a product with none shows no galaxies; the catalog's query count does not grow with the number of products.
11. Back-office tab: staff only; lists every review newest first with links to `#review-<pk>`; shows the empty state.
12. Seed data: every sample review's author and product appear together in a Delivered seeded order, every rating level appears, one product has more than ten, and none is by `customer`, read from the seed's constants without invoking the command.

## Out of Scope

- An approval queue, a "Report" button, or any automatic text filtering.
- Sorting or filtering reviews on the product page (by galaxies, with photos, and so on).
- More than one photo per review.
- Replies to reviews, from staff or from other customers.
- "Was this helpful?" votes.
- A dashboard panel for ratings.
- Notifying a customer when their review is removed or edited by staff.
- A Returned order status, or recording when an order was delivered.
- Reviews by visitors, or by anyone without a Delivered order.

## Further Notes

- Removing a review when its purchase stops counting was chosen deliberately: a product that was sent back does not earn a review. The cost is that a staff slip which moves an order off Delivered destroys the review for good.
- The clean-up runs from the back-office status view. A status changed in Django's admin site, or directly in the database, does not trigger it.
- The SoulSear Mark I sample order is a real seeded order worth $1.2M. It is outside the dashboard's default 30-day view but will appear in any range long enough to include it.
- The repository tracks a `db.sqlite3` snapshot for grading. Applying this feature's migration and re-running `seed` changes that file; whether to commit the updated snapshot is a separate decision.
