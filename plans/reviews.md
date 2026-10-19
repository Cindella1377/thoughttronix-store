# Plan: Product Reviews

> Source PRD: `prd/reviews.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: a new `reviews` app, namespace `reviews`. It touches other apps only at their edges: the product page and catalog cards include its partials, the back-office rail gains a Reviews tab, the order-status view calls its clean-up rule, and `seed` creates sample reviews.
- **Model**:
  - `Review` — product (FK, cascade), author (FK to the user, cascade), `rating` (`Review.Rating`, an `IntegerChoices`: 1 Black hole, 2 Space junk, 3 Low orbit, 4 Stellar, 5 Out of this world), `body` (optional, ≤ 2,000 characters), `image` (optional, `upload_to="reviews/"`), `created_at`, `updated_at` (null until the first edit), `edited_by_staff`. A `UniqueConstraint` on product and author. Ordered newest first.
  - The rules live on the model and its manager: `Review.objects.eligibility(user, product)`, `Review.objects.remove_unqualified(order)`, `Review.can_edit(user)`, and `Product.objects.with_rating()`. No service module.
- **Confirmed buyer**: an order with status Delivered whose items include the product. Checked when writing; `remove_unqualified` deletes a review once its author has no Delivered order for the product left.
- **Eligibility statuses**: `signed_out`, `can_review`, `has_reviewed`, `on_its_way`, `staff`, `not_a_buyer`.
- **URLs**: all named in the `reviews` namespace; writes use pks.

  | Name | Path |
  |---|---|
  | `create` | `/reviews/new/<product_pk>/` |
  | `more` | `/reviews/product/<product_pk>/?page=<n>` |
  | `edit` | `/reviews/<pk>/edit/` |
  | `card` | `/reviews/<pk>/` |
  | `confirm_delete` | `/reviews/<pk>/delete/` |
  | `manage` | `/manage/reviews/` |

- **Authorization**: only `can_review` may create. The author and any staff user may edit and delete; anyone else gets a 404. The Reviews tab is staff only.
- **Front end**: HTMX partials under `templates/reviews/partials/_<name>.html`, never extending `base.html`. Every write response also swaps the summary out-of-band. The galaxy is one inline SVG; the picker is five radio buttons. Delete confirms inline, never with `hx-confirm`. No JavaScript beyond HTMX.
- **Display**: the reviewer's first name, falling back to the username, never the email. Cards are anchored `#review-<pk>`; the section is anchored `#reviews`.

*Each phase is written test-first: the tests named in a phase are written before the code they cover, and the phase ends only when they pass alongside the rest of the suite and Ruff is clean.*

---

## Phase 1: Write a Review

**User stories**: 1, 4, 6 (without the photo), 7, 8, 9 (rating and text), 10, 19

### What to build

The thinnest path from a Delivered order to a review on the product page. The `reviews` app, the `Review` model with its `Rating` choices, and one migration (the photo field included, unused until Phase 6). A conftest fixture for a Delivered order of `product` by `customer`. The product page gains a reviews section: a summary with the galaxy average and count, or "No reviews yet"; a form for a Delivered buyer with the galaxy picker (each level's name shown as it is chosen) and an optional text box; and the list of reviews, newest first, each card showing its galaxies, level name, first name, posted date, and text. Submitting with HTMX replaces the form with the new card and refreshes the summary out-of-band. After posting, the form does not come back. In this phase everyone who cannot review sees nothing in the form's place.

### Acceptance criteria

- [ ] A Delivered buyer can post a rating with or without text; the response is the card partial plus the out-of-band summary with the new average and count
- [ ] A POST from anyone without a Delivered order makes no review
- [ ] A second review of the same product is refused by the form and by the database constraint
- [ ] A missing rating and text over 2,000 characters return the form with its error and the entered values
- [ ] Reviews list newest first; a product with none shows the designed empty state
- [ ] Cards show the first name, falling back to the username, and never the email
- [ ] The galaxy partial has an `aria-label` such as "4 out of 5 galaxies, Stellar"
- [ ] Manual: as `customer`, open DreamWeaver, post 4 galaxies, and watch the form become your card and the count go to 1 without a reload

---

## Phase 2: Who Sees the Form

**User stories**: 3, 16, 17, 20, 24

### What to build

`Review.objects.eligibility(user, product)` with all six statuses, and the form's place switching on it. Signed-out visitors get "Sign in to review a product you've received", linking to sign-in with `next` back to the product's `#reviews`. Placed or Shipped orders get "Your order's on its way. You can review it once it's delivered." Never ordered, or only Cancelled orders, get "Reviews come from customers who've received this product." Staff with no Delivered order see nothing; staff with one review like anyone else. Unavailable products follow the same rules. The create view refuses anything but `can_review`.

### Acceptance criteria

- [ ] Each of the six statuses comes from the order history that produces it, including Cancelled-only giving `not_a_buyer` and staff with and without their own Delivered order
- [ ] Each status renders its message, or nothing for `staff` and `has_reviewed`
- [ ] The sign-in link's `next` returns to the product page's `#reviews`
- [ ] A Delivered buyer of an unavailable product can review it
- [ ] Manual: as `customer`, open Veil (Placed) and Seraphine Mini (Shipped) and see "on its way"; sign out and see the sign-in link

---

## Phase 3: Returns Remove Reviews

**User stories**: 18, 27

### What to build

`Review.objects.remove_unqualified(order)`: for each product on the order, delete the order's customer's review of it if they no longer have a Delivered order containing it. Reviews are deleted one by one, so Phase 6 can delete photo files with them. `UpdateOrderStatusView` calls it after saving a new status. Any move away from Delivered counts. Moving back to Delivered unlocks the form again but restores nothing.

### Acceptance criteria

- [ ] Moving the only Delivered order to Cancelled removes the review; so does moving it to Shipped
- [ ] A second Delivered order for the same product keeps the review
- [ ] Reviews of products not on the order, and other customers' reviews, are untouched
- [ ] Moving the order back to Delivered shows the form again, with no review restored
- [ ] Manual: review DreamWeaver as `customer`, cancel that order in the back office, and see the review gone and "Reviews come from customers who've received this product"

---

## Phase 4: Edit and Delete Your Own

**User stories**: 11, 12, 14, 15, 21

### What to build

`Review.can_edit(user)`, true for the author (staff comes in Phase 5). The author's own card shows Edit and Delete and is pinned at the top of the list. Edit swaps the card for the form in place; Save swaps the updated card back and refreshes the summary, Cancel swaps the unchanged card back. Saving sets `updated_at`, and the card shows "edited <date>". Delete swaps the card's buttons for "Delete this review? Yes, delete · Keep it"; Yes removes the card, re-renders the form's place so the author can review again, and refreshes the summary; Keep it brings the buttons back. Other customers and visitors get a 404 from every one of these endpoints.

### Acceptance criteria

- [ ] The author can edit; the response is the card and the out-of-band summary; an invalid edit returns the form with errors and entered values
- [ ] An edit sets `updated_at` and the card shows "edited"; an unedited review shows no marker
- [ ] Cancel and Keep it return the card unchanged
- [ ] Yes, delete removes the review, returns the form in its place, and updates the summary
- [ ] Another customer and a visitor get a 404 from edit, card, and delete, and nothing changes
- [ ] The viewer's own review is first in the list and not repeated further down
- [ ] Manual: edit your review in the middle of a long page and confirm the page does not jump; delete it, choose Keep it, then delete it for real

---

## Phase 5: Staff Moderation

**User stories**: 22, 23, 25, 26

### What to build

`can_edit` becomes true for any staff user. Staff see Edit and Delete on every card and use the same in-place flows. A staff edit of someone else's review sets `edited_by_staff`, and the card shows "edited by ThoughtTronix staff <date>"; a later edit by the author sets it back to plain "edited". The back-office rail gains a Reviews tab, `/manage/reviews/`, staff only: every review newest first, paginated, with product, galaxies, author, posted date, the start of the text, and the edit marker, each row linking to `<product url>#review-<pk>`. A designed empty state when there are none.

### Acceptance criteria

- [ ] Staff can edit and delete any review in place
- [ ] A staff edit sets `edited_by_staff`; a later author edit clears it; the card shows the matching marker
- [ ] The Reviews tab is staff only, lists newest first, and links each row to `#review-<pk>`
- [ ] The tab is active when on the Reviews page, and shows its empty state with no reviews
- [ ] Manual: as `employee`, open the Reviews tab, follow a row to its product page, and edit that review

---

## Phase 6: Photos

**User stories**: 6 (the photo), 9 (the photo), 13

### What to build

The form gains its optional photo, posted with `hx-encoding="multipart/form-data"`. The 2 MB rule and its message move out of `products/forms.py` to a place both forms import; the product form keeps behaving exactly as before. Cards show the photo as a thumbnail linking to the full-size image. Editing uses the clearable file input to keep, replace, or remove the photo, and replacing or removing deletes the old file. Deleting a review, by its author, by staff, or by `remove_unqualified`, deletes its photo file.

### Acceptance criteria

- [ ] A review can be posted with a photo, and its card shows the thumbnail and full-size link
- [ ] A photo over 2 MB returns the form with the error; the product form's limit and message are unchanged
- [ ] An edit can keep, replace, or clear the photo; replacing or clearing deletes the old file
- [ ] Deleting a review deletes its photo file, including through `remove_unqualified`
- [ ] Manual: post a review with a photo, replace it, then remove it, without a reload

---

## Phase 7: Confirmed-Buyer Badge and Show More

**User stories**: 5

### What to build

Each card gains "Confirmed buyer · bought <Mon YYYY>", the month of the author's most recent Delivered order containing the product, fetched in the list query as a subquery annotation. The list shows ten reviews (after the viewer's own, if any); while more remain, a "Show more reviews" button fetches the next ten and adds them below the last card, with the next button or none at the end.

### Acceptance criteria

- [ ] The badge shows the month of the most recent Delivered order for that product
- [ ] Listing a page of reviews runs the same number of queries whatever the number of reviews
- [ ] The first page shows ten; "Show more" adds the next ten below; the button is gone on the last page
- [ ] The viewer's own review never appears twice across pages
- [ ] Manual: with more than ten reviews, tap "Show more reviews" and confirm the page does not jump

---

## Phase 8: Catalog Ratings

**User stories**: 2

### What to build

`Product.objects.with_rating()` annotates average rating and review count in one query. The catalog and category views use it, and each card shows the galaxy partial with the average and count when the count is above zero, and nothing otherwise. The product page's summary uses the same annotation.

### Acceptance criteria

- [ ] `with_rating()` gives the right average and count, and zero for a product with none
- [ ] A card with reviews shows its galaxies and count; one without shows nothing
- [ ] The catalog's query count does not grow with the number of products
- [ ] Manual: review two products and see their galaxies on the catalog cards

---

## Phase 9: Seeded Samples

**User stories**: 28, 29

### What to build

The seed writes 15 to 25 fixed sample reviews from a constant, in the store's voice, each by a background customer for a product that customer has a Delivered seeded order for; the seed checks this. Every galaxy level appears, one product has more than ten, and one review has `edited_by_staff` set. The demo `customer` writes none. The seed also adds one background customer's Delivered SoulSear Mark I order, dated before the 2024 recall, with a 1-galaxy Black hole review.

### Acceptance criteria

- [ ] Every sample's author and product appear together in a Delivered seeded order, the Mark I order included, read from the seed's constants without invoking the command
- [ ] Every rating level appears, one product has more than ten samples, one is staff-edited, and none is by `customer`
- [ ] The Mark I order is older than the background orders' 182-day span
- [ ] Manual: run `seed`, open the product with more than ten reviews and tap "Show more", open SoulSear Mark I and see the Black hole review, and see galaxies on the catalog
