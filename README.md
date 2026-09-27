# The ThoughtTronix Store

*Your Thoughts, Our Business.*

A server-rendered Django 6 storefront and back office for the world's most
beloved consumer neural technology: browse the catalog, fill a cart, check
out through a fully validated form, and — if you're staff — run the store
from the back office, analytics dashboard included.

## Getting started

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). No Node.js —
Tailwind runs as a standalone binary.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py tailwind runserver
```

Then open <http://127.0.0.1:8000/>. From clone to browsing the store, this
takes about two minutes.

## Demo logins

The `seed` command creates a fixed demo world — the same one every run:

| Username   | Password      | Who they are                                                  |
| ---------- | ------------- | ------------------------------------------------------------- |
| `admin`    | `admin123`    | Superuser: everything below, plus the Django admin at `/admin/` |
| `employee` | `employee123` | Staff: the back office (products, orders, coupons, dashboard)  |
| `customer` | `customer123` | A customer with order history and a live cart                  |

## Demo coupons

Coupons are percent or dollar amounts off, run between two dates, and are
entered on the cart page. When a coupon expires, the store swaps it for its
staff-chosen replacement — or the public coupon whose savings on the cart
are closest — and tells the customer why. The seed dates them relative to
today, so the demo never goes stale:

| Code          | Discount            | What it demonstrates                                           |
| ------------- | ------------------- | -------------------------------------------------------------- |
| `THOUGHTS10`  | 10% off, expired    | The `customer` cart holds it: open the cart to see the swap    |
| `THOUGHTS15`  | 15% off, expired    | The middle of the chain THOUGHTS10 → THOUGHTS15 → THOUGHTS20   |
| `THOUGHTS20`  | 20% off             | Where the chain ends up                                        |
| `SUMMER5`     | $5 off, expired     | No replacement set: falls back to the closest public coupon    |
| `FALL10`      | 10% off, public     | Part of the public pool                                        |
| `SAVE15`      | $15 off $75+, public| A minimum order: drop below $75 and the coupon pauses          |
| `WELCOME5`    | $5 off, once each   | `customer` already used it: applying it again swaps it         |
| `HOLIDAY20`   | 20% off, scheduled  | Starts Nov 25; the back office lists it as scheduled           |
| `STAFFONLY50` | 50% off, private    | Works if typed, but never offered as a replacement             |

Staff manage coupons in the back office's Coupons tab.

## Commands

| Command                                     | What it does                             |
| ------------------------------------------- | ---------------------------------------- |
| `uv sync`                                    | Install dependencies                     |
| `uv run python manage.py migrate`            | Apply database migrations                |
| `uv run python manage.py seed`               | Reset the database to the demo world (destructive, idempotent) |
| `uv run python manage.py tailwind runserver` | Dev server + Tailwind watch              |
| `uv run python manage.py tailwind build`     | Compile production CSS                   |
| `uv run pytest`                              | Run the test suite                       |
| `uv run ruff check .`                        | Lint                                     |
| `uv run ruff format .`                       | Format                                   |

## Repo layout

`config/` is the project package (settings, root URLs); the four apps are
`accounts` (custom user model), `products` (the public catalog and its
back-office CRUD), `orders` (cart, checkout, orders, and coupons — with
`place_order` and the coupon swap in `orders/services.py`), and `dashboard` (staff
analytics, with the aggregations in `dashboard/queries.py`). Project-level
templates live in `templates/`, static sources in `assets/`. The product
requirements are in `prd/`, the phase-by-phase build plan in `plans/`, and
`PROMPTS.md` is where AI usage on this codebase gets logged.
