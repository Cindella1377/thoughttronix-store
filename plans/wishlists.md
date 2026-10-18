# Plan: Wishlists

> Source PRD: `prd/wishlists.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: a new `wishlists` app, namespace `wishlists`. It touches other apps only at their edges: catalog and product templates include its partials, the navbar gains its icon, a context processor supplies the main list's contents, the account page gains a first-name form, and `seed` creates sample lists.
- **Models**:
  - `Wishlist` — owner (FK to the user, cascade), `name` (≤ 50 characters), `is_main`, `share_token` (nullable, unique), `is_public`, `is_sample`, created timestamp. A `UniqueConstraint` on owner and `Lower("name")`; a conditional `UniqueConstraint` allowing one `is_main` list per owner.
  - `WishlistItem` — wishlist (cascade), product (cascade), `position`, added timestamp. A `UniqueConstraint` on wishlist and product. Ordered by `position`; new items take a position above every existing one.
  - The rules live on the models and their manager: `Wishlist.objects.main_for(user)`, `add`, `remove`, `toggle`, `move_up`, `move_down`, `make_main`, `set_link_sharing`. No service module.
- **URLs**: all named in the `wishlists` namespace. Owner pages use pks; share links use the token; public pages use the username.

  | Name | Path |
  |---|---|
  | `index` | `/wishlists/` |
  | `detail` | `/wishlists/<pk>/` |
  | `rename` | `/wishlists/<pk>/rename/` |
  | `delete` | `/wishlists/<pk>/delete/` |
  | `make_main` | `/wishlists/<pk>/main/` |
  | `link_sharing` | `/wishlists/<pk>/share/` |
  | `public_toggle` | `/wishlists/<pk>/public/` |
  | `item_remove` | `/wishlists/<pk>/items/<item_pk>/remove/` |
  | `item_move` | `/wishlists/<pk>/items/<item_pk>/<up\|down>/` |
  | `lamp` | `/wishlists/lamp/<product_pk>/` |
  | `save_to` | `/wishlists/save/<product_pk>/<pk>/` |
  | `shared` | `/wishlists/shared/<token>/` |
  | `public` | `/wishlist/<username>/` |

- **Authorization**: every owner view requires sign-in and looks lists up through the signed-in user's own lists, so another user's list is a 404. Shared and public pages need no sign-in and are read-only. Staff and admin are treated exactly like customers.
- **Visitors who are not signed in**: every wishlist control renders as a plain link to sign in with `next` set to the current page, as `orders/partials/_add_button.html` already does.
- **Front end**: HTMX partials under `templates/wishlists/partials/_<name>.html`; DaisyUI's CSS-only dropdown; the smoke is a CSS animation in `assets/css/source.css`. No JavaScript beyond HTMX.

*Each phase is written test-first: the tests named in a phase are written before the code they cover, and the phase ends only when they pass alongside the rest of the suite and Ruff is clean.*

---

## Phase 1: The Genie Lamp

**User stories**: 4, 8, 9, 10, 13, 29

### What to build

The thinnest path from a catalog thumbnail to a saved product. The `wishlists` app, both models, and one migration. Every catalog thumbnail carries the lamp: tapping it as a signed-in user toggles the product in their main list, creating "My Wishlist" as main the first time. An add returns a gold lamp with a one-time smoke puff; a remove returns the outline lamp with no smoke. A context processor supplies the main list's product IDs so every lamp renders in the right state, without creating a list. Visitors who are not signed in get the sign-in link. A lamp icon in the navbar opens a bare `/wishlists/` page that lists the main list's items, and the account page links there. Staff get all of this exactly as customers do.

### Acceptance criteria

- [ ] `main_for` creates "My Wishlist" as main once, and returns the same list after; the database refuses a second main list for one owner
- [ ] A product cannot appear twice in one list
- [ ] The lamp endpoint adds, then removes, a product from the main list; the add response carries the smoke class and the remove response does not
- [ ] The catalog renders a gold lamp for products in the main list and an outline lamp otherwise; a user with no lists sees only outlines and no list is created
- [ ] An unavailable product can be removed by the lamp but not added
- [ ] A visitor who is not signed in sees the lamp as a sign-in link that returns to the catalog
- [ ] The navbar lamp and the account page link reach `/wishlists/`, which shows the main list's items, and requires sign-in
- [ ] The lamp has an `aria-label` saying whether it will add or remove
- [ ] Manual: tap a lamp in the catalog, watch the smoke, reload and see it still gold, then tap it back to an outline

---

## Phase 2: Looking After a List

**User stories**: 19, 26, 27

### What to build

The owner's list page, `/wishlists/<pk>/`, showing each item with its photo, name, price, and add-to-cart button. Each item gets a ✕ that removes it with HTMX. A product the store has stopped selling stays on the list, greyed and marked "No longer available", without "Add to cart"; a deleted product drops off every list. An empty list shows a designed empty state with a link to the catalog. `/wishlists/` links each list to its page.

### Acceptance criteria

- [ ] An owner can open their list; another user's list 404s
- [ ] ✕ removes an item and re-renders the list without a reload; removing the last item shows the empty state
- [ ] An unavailable product shows "No longer available" and no "Add to cart", and shows normally again when made available
- [ ] Deleting a product removes it from every list
- [ ] An empty list shows the designed empty state
- [ ] Manual: save two products, remove one with ✕, then mark the other unavailable in the back office and see it greyed

---

## Phase 3: Several Lists

**User stories**: 14, 15, 16, 17, 18

### What to build

`/wishlists/` becomes the full lists page: a "+ New list" form, every list with its item count, and a star on the main list. The owner can create a list, rename one at `/wishlists/<pk>/rename/`, star any list as main, and delete a list at `/wishlists/<pk>/delete/` through a confirmation page naming the list and its item count. The list form refuses a name matching another of the owner's lists in any capitalisation, a name over 50 characters, and a 21st list. The main list cannot be deleted until another is starred. A user with no lists sees a designed empty state.

### Acceptance criteria

- [ ] Names are unique per owner ignoring capitalisation, enforced by the form and backstopped by the database; two owners may share a name
- [ ] The form rejects a name over 50 characters and a 21st list, with the error shown on the form
- [ ] Renaming follows the same rules, and keeping the same name is allowed
- [ ] `make_main` stars one list and unstars the others; the lamp then adds to the newly starred list
- [ ] Deleting the main list is refused; deleting another list goes through the confirmation page and removes its items
- [ ] Another user's list 404s on rename, star, and delete
- [ ] Manual: create "Birthday", star it, tap a lamp in the catalog, and find the product in "Birthday"

---

## Phase 4: The Product Page

**User stories**: 11, 12

### What to build

Beside "Add to cart" on the product page, a button that adds the product to the main list or removes it, and a "Save to…" DaisyUI dropdown listing every list with a tick on those that already hold the product. Choosing a list toggles the product there. The button and dropdown are one partial, swapped together after any change so they always agree. The dropdown ends with a "+ New list" link to `/wishlists/`. Visitors who are not signed in see the sign-in link; an unavailable product can be removed but not added.

### Acceptance criteria

- [ ] The main button reads add or remove according to the main list, and toggles it without a reload
- [ ] The dropdown ticks every list holding the product, and choosing one adds or removes it there
- [ ] After any change, the button and the ticks both reflect the new state
- [ ] Toggling a list belonging to another user 404s
- [ ] A visitor who is not signed in sees a sign-in link that returns to the product page
- [ ] Manual: on one product page, save to "My Wishlist" and "Birthday", remove from "Birthday" through the dropdown, and check both lists

---

## Phase 5: Reordering

**User stories**: 20, 21

### What to build

↑ and ↓ buttons on each item of the owner's list page. Each tap moves the item one place and re-renders the list with HTMX. The top item has no ↑ and the bottom item no ↓. Items added later, from anywhere, still land at the top.

### Acceptance criteria

- [ ] `move_up` and `move_down` swap the item with its neighbour, and do nothing at the ends
- [ ] The move endpoint re-renders the list in the new order; another user's item 404s
- [ ] A product added after a reorder appears at the top
- [ ] Manual: move the bottom item to the top, add a new product from the catalog, and see it above everything

---

## Phase 6: Share by Link

**User stories**: 1, 3, 7, 22, 23, 28

### What to build

A "Share by link" switch on each list. Turning it on stores a fresh random token and shows the link to copy; turning it off clears the token. Turning it on again gives a new token, and the old link never works again. `/wishlists/shared/<token>/` shows the list read-only to anyone: no switches, star, ✕, or arrows. It is headed with the owner's name (the username until Phase 7 adds first names) and never shows their email or other lists. Each item shows "Add to cart" and the lamp, which acts on the viewer's own main list; a visitor who is not signed in is sent to sign in and returned to the shared list.

### Acceptance criteria

- [ ] Turning sharing on stores a token; turning it off makes the shared page 404; turning it on again gives a different token
- [ ] Turning on a list that is already shared keeps its token
- [ ] The shared page shows items without any owner controls, the owner's email, or other lists
- [ ] A signed-in viewer's lamp saves the item to the viewer's own main list, not the owner's
- [ ] A visitor who is not signed in can view the page, and its buttons are sign-in links back to it
- [ ] A list with sharing off is reachable only by its owner
- [ ] Manual: share a list, open the link in a private window, sign in from there and save an item, then turn sharing off and see the link stop working

---

## Phase 7: Public Page and First Name

**User stories**: 2, 5, 6, 24, 25

### What to build

A "Show on my public page" switch on each list, independent of link sharing. `/wishlist/<username>/` shows every public list of that user, read-only, in the same shape as the shared page. A real user with nothing public gets a designed empty state with a catalog link; an unknown username is a 404. The account page gains an optional first-name form beside the change-email form. Shared and public pages head lists with the first name, falling back to the username, and `/wishlists/` prompts owners with a blank first name to add one.

### Acceptance criteria

- [ ] The public switch toggles independently of link sharing
- [ ] The public page shows only public lists; a list that is shared by link but not public does not appear
- [ ] A real user with no public lists gets the empty state; an unknown username 404s
- [ ] The first-name form saves and clears the name, with a success message
- [ ] Shared and public headings use the first name, and the username when it is blank
- [ ] The first-name prompt appears on `/wishlists/` only when the name is blank
- [ ] Manual: make "Birthday" public, set a first name, and open `/wishlist/<username>/` signed out

---

## Phase 8: Seeded Samples

**User stories**: 30, 31

### What to build

`seed` gives each demo user (`admin`, `employee`, `customer`) an empty "My Wishlist" as main, plus sample lists marked `is_sample` that show every sharing state: `customer` gets "Birthday" (public) and "Gift ideas" (shared by link), and `employee` gets "Staff picks" (public). Every page that shows a sample list shows a "Sample list" badge. Sample lists are never main, so owners can delete them like any other list.

### Acceptance criteria

- [ ] The sample-list constants name only demo users, mark every list `is_sample`, and never make one main — tested from the constants without invoking the command
- [ ] The "Sample list" badge appears on the owner's pages, the shared page, and the public page for sample lists only
- [ ] A sample list can be deleted through the normal confirmation page
- [ ] Manual: run `seed`, sign in as `customer`, and see both sample lists badged; open `/wishlist/employee/` signed out and see "Staff picks"
