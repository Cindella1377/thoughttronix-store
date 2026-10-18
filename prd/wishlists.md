# PRD: The ThoughtTronix Store — Wishlists

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

*Builds on `prd/core-platform.md` and `prd/account-email.md`. Where this document is silent, the core PRD's conventions hold.*

---

## Problem Statement

A shopper who likes a product but is not ready to buy it has nowhere to keep it. The cart is the only place a product can be saved, and the cart is for buying now: it holds quantities, carries coupons, and empties at checkout. There is no way to collect products for later, to sort them by purpose ("Birthday", "Home office"), or to show them to someone else.

That last gap also costs the store visitors. A shopper who wants a gift has no link to send to family and friends, so the people most likely to buy for them never land on the site. A list worth sharing is a reason for a stranger to visit, browse, and sign up.

## Solution

**Several named lists.** A signed-in shopper keeps any number of wishlists, up to twenty, each with its own name. The first time they save anything, a list called "My Wishlist" is created for them and starred as their main list. They can star a different list at any time.

**The genie lamp.** Every product thumbnail in the catalog carries a small genie-lamp icon. An outline lamp means the product is not in the shopper's main list. Tapping it adds the product: the lamp turns gold and puffs smoke. Tapping a gold lamp removes the product and the lamp returns to an outline. The page never reloads.

**The product page.** Beside "Add to cart", a button adds the product to the main list or removes it, and a "Save to…" dropdown lists every list with a tick on the ones that already hold the product. Choosing a list adds or removes the product there. The page never reloads.

**Managing lists.** A lamp icon in the navbar opens the shopper's wishlists page, which the account page also links to. There they create, rename, star, and delete lists, and open any list to see its items, remove an item, or move items up and down. Items appear newest first until the owner moves them.

**Sharing.** Each list has two switches. "Share by link" creates a private link the owner can send to anyone; turning it off kills the link, and turning it back on makes a new one. "Show on my public page" puts the list on the owner's public page, `/wishlist/<username>/`. Lists with neither switch on are seen only by their owner.

**Viewing a shared list.** Anyone with the link, or anyone visiting a public page, can see the list without an account. The page names the owner by first name, falling back to the username. Each item offers "Add to cart" and the genie lamp, so a signed-in viewer can save the item to their own main list. A visitor who is not signed in is sent to sign in, then returned to the list.

**A first name on the account page.** The account page gains an optional "First name" field, so shared lists can say whose they are.

## User Stories

**Visitor**

1. As a visitor, I can open a list someone shared with me by link and see its items, prices, and photos without an account.
2. As a visitor, I can open someone's public page and see every list they made public.
3. As a visitor, tapping "Add to cart" or a genie lamp on a shared list takes me to sign in and brings me back to the same list afterwards.
4. As a visitor, I see a genie lamp on catalog thumbnails; tapping it takes me to sign in.
5. As a visitor, a public page for a real user with nothing public tells me they have not shared any lists yet and offers a link to the catalog.
6. As a visitor, a public page for a username that does not exist shows the store's "page not found".
7. As a visitor, a share link that was turned off or replaced shows the store's "page not found".

**Customer (owner)**

8. As a customer, the first time I save a product, a list called "My Wishlist" is created for me and starred as my main list.
9. As a customer, I can tap the genie lamp on a catalog thumbnail to add the product to my main list; the lamp turns gold and puffs smoke without the page reloading.
10. As a customer, I can tap a gold lamp to remove the product from my main list; the lamp returns to an outline without the page reloading.
11. As a customer, on a product page I can add the product to my main list or remove it with one button.
12. As a customer, on a product page I can open "Save to…", see which of my lists already hold the product, and add it to or remove it from any of them.
13. As a customer, the navbar lamp icon takes me to my wishlists page, and my account page links there too.
14. As a customer, I can create a list by name, and rename it later.
15. As a customer, I am told when a new or renamed list's name matches one of my other lists, whatever its capitalisation, or is over 50 characters, or when I already have 20 lists.
16. As a customer, I can star any list as my main list; exactly one list is starred at a time.
17. As a customer, I cannot delete my main list until I have starred another one.
18. As a customer, deleting a list first shows a page that names the list and how many items it holds, and asks me to confirm.
19. As a customer, I can open any of my lists and remove an item with its ✕ button, without the page reloading.
20. As a customer, my lists show the newest item first, and I can move any item up or down one place at a time without the page reloading.
21. As a customer, a product I add always goes to the top of the list, even after I have reordered it.
22. As a customer, I can turn "Share by link" on to get a link I can copy, and turn it off to make that link stop working.
23. As a customer, turning "Share by link" back on gives me a new link; the old one never works again.
24. As a customer, I can turn "Show on my public page" on or off for each list, separately from its link.
25. As a customer, I can set or clear my first name on my account page, and my shared lists show it.
26. As a customer, a product the store stops selling stays on my lists marked "No longer available", without an "Add to cart" button, and returns to normal if the store sells it again.
27. As a customer, a product the store deletes disappears from my lists.
28. As a customer, I can view someone else's shared list and use its lamps to save items to my own main list.

**Employee (staff) and admin**

29. As an employee or admin, I have wishlists, lamps, and sharing exactly as customers do.

**Any developer**

30. As a developer, `seed` gives each demo user an empty "My Wishlist" as their main list, plus sample lists that show every sharing state, each marked "Sample list" wherever it appears.
31. As a developer, an owner can delete a sample list like any other.

## Implementation Decisions

**A new app.** `wishlists` owns the models, views, templates, and URLs. It touches other apps only at their edges: the catalog and product templates include its partials, the navbar gains its icon, a context processor supplies the main list's contents, the account page gains a first-name form, and `seed` creates sample lists.

**Models.**

- `Wishlist`: owner (foreign key to the user, cascading on delete), `name` (up to 50 characters), `is_main`, `share_token` (nullable, unique), `is_public`, `is_sample`, and a creation timestamp.
  - A `UniqueConstraint` on owner and `Lower("name")` enforces unique names per owner, ignoring capitalisation.
  - A conditional `UniqueConstraint` on owner where `is_main` is true allows at most one main list per owner.
  - Ordered by name on the wishlists page, with the main list first.
- `WishlistItem`: wishlist (cascade), product (cascade, so deleting a product removes it from every list), `position`, and an added timestamp. A `UniqueConstraint` on wishlist and product stops a product appearing twice in one list. Items are ordered by `position`.

**The rules live on the models.** Logic stays in models and managers, per the architecture convention. No service module is added; `CLAUDE.md` names exactly two, and nothing here is a cross-model workflow on the scale of `place_order`.

- `Wishlist.objects.main_for(user)` returns the user's main list, creating "My Wishlist" as main if they have no lists.
- `Wishlist.add(product)` and `Wishlist.remove(product)`. Adding gives the item a position above every existing item, so it lands on top. Adding a product already in the list does nothing.
- `Wishlist.toggle(product)` adds or removes and reports which it did. The lamp and the main button use it.
- `Wishlist.move_up(item)` and `Wishlist.move_down(item)` swap positions with the neighbour; at the top or bottom they do nothing.
- `Wishlist.make_main()` unstars the owner's other lists and stars this one, in one transaction.
- `Wishlist.set_link_sharing(on)`: on stores a fresh random token (`secrets.token_urlsafe`), off sets it to null. Turning on a list that is already on does not change its token.
- Deleting the main list is refused in the model's `delete` and in the view.
- The 20-list cap and the name rules are checked in the list form, with the database constraint as the backstop for names.

**Who owns a list.** Owner views look lists up through the signed-in user's own lists, so a list belonging to someone else is a 404, never a 403.

**The lamp.** `templates/wishlists/partials/_lamp.html` renders the lamp in both states for signed-in users, as an `hx-post` to the toggle endpoint that swaps itself. For visitors who are not signed in it is a plain link to sign in, with `next` set to the current page, exactly as `orders/partials/_add_button.html` does. The response after an add carries a class that plays a one-time smoke animation, defined in `assets/css/source.css`; a remove returns the outline lamp without it. The two lamp icons are inline SVG. The lamp has an `aria-label` that says whether it will add or remove.

**Knowing which products are saved.** A context processor supplies the IDs of products in the signed-in user's main list, as `orders/context_processors.py` already does for cart quantities, so the catalog renders every lamp in the right state with one query. It does not create a main list; a user with no lists sees every lamp as an outline.

**The product page.** `templates/wishlists/partials/_save_to.html` holds the main button and the "Save to…" dropdown, and is swapped as one piece after any change so the button and the ticks always agree. The dropdown is DaisyUI's CSS-only dropdown; no JavaScript is added. It includes a "+ New list" link to the wishlists page. A product the store has stopped selling can be removed from lists but not added to them.

**Lists that are not for sale.** An unavailable product stays on lists, marked "No longer available", greyed, and without "Add to cart". The add-to-cart partial already renders its own disabled state for unavailable products.

**Shared and public pages.** Both use one list template in read-only mode: no switches, no star, no ✕, no arrows. Each item shows the existing add-to-cart partial and the lamp partial, which acts on the viewer's own main list. The heading is "<first name>'s <list name>", falling back to the username. The owner's email and their private lists are never shown. An owner who opens their own shared link sees the read-only page, as a viewer would.

**Public page.** A real user with no public lists gets a designed empty state with a catalog link. An unknown username is a 404. Whether a username exists is already revealed by signup, so this discloses nothing new.

**Reordering.** ↑ and ↓ buttons on each item post to an endpoint that moves it and re-renders the item list partial. No drag-and-drop: the project allows no JavaScript beyond HTMX. A drag library could later call the same move logic.

**First name.** The account page gains a small form for `first_name` alone, beside the change-email form, saving with a success message. The wishlists page shows "Add your first name so friends recognise your lists" with a link to it when the name is blank.

**Navbar.** A lamp icon linking to the wishlists page sits beside the cart badge for signed-in users.

**Seed.** Each of the three demo users (`admin`, `employee`, `customer`) gets an empty "My Wishlist" as their main list, which is not a sample. Sample lists, all marked `is_sample`, show each sharing state:

- `customer`: "Birthday", public; "Gift ideas", shared by link.
- `employee`: "Staff picks", public.

Sample lists are never starred as main, so their owners can always delete them. Every page that shows a sample list shows a "Sample list" badge. Share tokens are random, so seeded links change each time `seed` runs.

**URLs.** All named in the `wishlists` namespace. Owner pages use pks, like the back office. Share links use the token, and public pages use the username:

| Name | Path | Page |
|---|---|---|
| `index` | `/wishlists/` | The owner's lists, the new-list form, switches, and stars |
| `detail` | `/wishlists/<pk>/` | One of the owner's lists, with ✕ and ↑/↓ |
| `rename` | `/wishlists/<pk>/rename/` | Rename a list |
| `delete` | `/wishlists/<pk>/delete/` | Confirm deleting a list |
| `make_main` | `/wishlists/<pk>/main/` | Star a list (POST) |
| `link_sharing` | `/wishlists/<pk>/share/` | Turn "Share by link" on or off (POST, HTMX) |
| `public_toggle` | `/wishlists/<pk>/public/` | Turn "Show on my public page" on or off (POST, HTMX) |
| `item_remove` | `/wishlists/<pk>/items/<item_pk>/remove/` | Remove an item (POST, HTMX) |
| `item_move` | `/wishlists/<pk>/items/<item_pk>/<up\|down>/` | Move an item (POST, HTMX) |
| `lamp` | `/wishlists/lamp/<product_pk>/` | Toggle a product in the main list (POST, HTMX) |
| `save_to` | `/wishlists/save/<product_pk>/<pk>/` | Toggle a product in a chosen list (POST, HTMX) |
| `shared` | `/wishlists/shared/<token>/` | A list shared by link |
| `public` | `/wishlist/<username>/` | A user's public lists |

The public page sits under `/wishlist/` (singular) so a username can never collide with an owner path such as `/wishlists/shared/`.

**Every list view has a designed empty state:** no lists yet, an empty list, a public page with nothing public.

## Testing Decisions

Tests use the shared fixtures in `conftest.py`, which already give `customer` and `staff_user` distinct emails. Tests never invoke the seed command. Nothing here depends on time, so no `now` argument is needed.

Coverage, in priority order:

1. Model rules: `main_for` creates "My Wishlist" once and returns it after; one main list per owner; `make_main` moves the star; the main list cannot be deleted; names are unique per owner ignoring capitalisation but may repeat across owners; a product cannot appear twice in one list.
2. Ordering: new items land on top, including after a reorder; `move_up` and `move_down` swap with the neighbour and do nothing at the ends.
3. Link sharing: turning on stores a token; turning off clears it and the old link 404s; turning on again gives a different token.
4. Privacy: an owner page for another user's list 404s; the shared page and public page never show owner controls, the owner's email, or private lists; a list with link sharing off and public off is reachable by no one but its owner.
5. The lamp: a signed-in toggle adds then removes; the add response carries the smoke class and the remove response does not; a visitor who is not signed in gets the sign-in link; an unavailable product can be removed but not added.
6. "Save to…": shows ticks for lists holding the product; toggles a chosen list; a list belonging to another user 404s.
7. List form: rejects a duplicate name in any capitalisation, a name over 50 characters, and a 21st list.
8. Public page: lists only public lists; a real user with none gets the empty state; an unknown username 404s.
9. Unavailable and deleted products: an unavailable product shows "No longer available" without "Add to cart"; deleting a product removes its items.
10. First name: the account form saves it; shared lists use it, and fall back to the username when blank.
11. Seed data: the sample-list constants name only demo users, mark every sample list `is_sample`, and never make one main, read from the seed's constants without invoking the command.

## Out of Scope

- **Staff points.** Staff public lists will later act as "staff picks", with a points system and staff-only dashboard for purchases made from them. That is its own feature, `prd/staff-picks.md`. This design leaves room for it: `is_sample` lets it ignore sample lists, and nothing here stops a cart item from recording which list it came from.
- Drag-and-drop reordering.
- Notes, quantities, sizes, or a "most wanted" star on items.
- Marking an item as bought, or hiding purchases from the owner.
- Sharing with specific accounts.
- Searching or browsing other people's public pages.
- Emailing a list from the site. Owners copy the link themselves.
- Price-drop or back-in-stock alerts.
- Wishlists for visitors who are not signed in.

## Further Notes

- Tapping a gold lamp removes the product from the main list with no confirmation. That was chosen deliberately: the gold lamp shows the state before the tap, and re-adding is one more tap.
- The repository tracks a `db.sqlite3` snapshot for grading. Applying this feature's migration and re-running `seed` changes that file; whether to commit the updated snapshot is a separate decision.
