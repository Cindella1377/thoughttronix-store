"""Order placement — one of the codebase's two deliberate deep modules.

The interface is the product: one function that turns a cart and a
validated checkout into an order, all-or-nothing. Callers never touch
``Order`` construction directly.

Coupons live here too, because keeping a cart's coupon valid spans the
cart, the coupons, and the customer's past orders: ``apply_coupon`` and
``refresh_cart_coupon`` swap an expired coupon for its replacement, chosen
by ``find_replacement``, and leave a notice on the cart saying why.
"""

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from .models import Cart, Coupon, Order, OrderItem

ADDRESS_FIELDS = [
    "email",
    "shipping_name",
    "shipping_street",
    "shipping_line2",
    "shipping_city",
    "shipping_state",
    "shipping_zip",
    "billing_name",
    "billing_street",
    "billing_line2",
    "billing_city",
    "billing_state",
    "billing_zip",
]


@transaction.atomic
def place_order(
    cart: Cart,
    user: AbstractBaseUser,
    checkout_data: Mapping[str, Any],
    *,
    coupon_code: str | None = None,
) -> Order:
    """Create an order from the cart's contents, then empty the cart.

    ``checkout_data`` is the ``cleaned_data`` of a valid ``CheckoutForm``.
    Addresses and line prices are denormalized onto the order — an order
    is a snapshot, immune to later catalog or address edits. Of the card,
    only the last four digits are stored; the full number and CVV never
    touch the database.

    All-or-nothing: runs in a transaction, so a failure partway through
    leaves no partial order and the cart intact.

    Raises ``ValueError`` if the cart is empty or holds a product that is
    no longer available.
    """
    lines = list(cart.lines())
    if not lines:
        raise ValueError("Cannot place an order from an empty cart.")
    unavailable = [line.product.name for line in lines if not line.product.is_available]
    if unavailable:
        raise ValueError(
            f"No longer available: {', '.join(unavailable)}. "
            "Remove them from the cart to check out."
        )

    card_digits = checkout_data["card_number"].replace(" ", "").replace("-", "")
    order = Order.objects.create(
        user=user,
        total=cart.total(),
        card_last4=card_digits[-4:],
        **{name: checkout_data[name] for name in ADDRESS_FIELDS},
    )
    for line in lines:
        OrderItem.objects.create(
            order=order,
            product=line.product,
            product_name=line.product.name,
            unit_price=line.product.price,
            quantity=line.quantity,
        )
    cart.items.all().delete()
    return order


class ChangeReason(enum.Enum):
    APPLIED = "applied"
    EXPIRED = "expired"
    NOT_STARTED = "not started"
    USED_UP = "used up"


@dataclass(frozen=True)
class CouponChange:
    """What happened to a cart's coupon: ``old`` gave way to ``new``.

    ``new`` is ``None`` when the coupon was removed with no replacement.
    """

    old: Coupon | None
    new: Coupon | None
    reason: ChangeReason


def apply_coupon(cart: Cart, code: str, *, now: datetime | None = None) -> CouponChange:
    """Put the coupon with ``code`` on ``cart``, replacing any coupon there.

    Codes match case-insensitively. A code that has expired, or that the
    customer has used up, goes through the same swap as a coupon that
    expires in the cart — see ``refresh_cart_coupon``.

    Raises ``ValueError`` for an unknown code or one that has not started;
    ``CouponApplyForm`` rejects both first, so customers see a form error.
    """
    now = now or timezone.now()
    coupon = Coupon.objects.filter(code=Coupon.normalize_code(code)).first()
    if coupon is None:
        raise ValueError(f"No coupon has the code {code!r}.")
    if now < coupon.starts_at:
        raise ValueError(f"{coupon.code} has not started yet.")

    old = cart.coupon
    cart.coupon = coupon
    cart.coupon_notice = ""
    cart.save(update_fields=["coupon", "coupon_notice"])
    change = refresh_cart_coupon(cart, now=now)
    return change or CouponChange(old=old, new=coupon, reason=ChangeReason.APPLIED)


def refresh_cart_coupon(
    cart: Cart, *, now: datetime | None = None
) -> CouponChange | None:
    """Keep ``cart``'s coupon valid, swapping it out if it no longer is.

    A coupon that has expired, is not currently running, or has been used
    up by the customer is replaced via ``find_replacement`` — or removed if
    nothing qualifies — and the cart's notice explains what happened. A
    coupon that is merely below its minimum is left alone: it is paused,
    not invalid (see ``Cart.discount``).

    Returns the change, or ``None`` if the coupon was fine as it was.
    """
    now = now or timezone.now()
    coupon = cart.coupon
    if coupon is None:
        return None
    if coupon.is_expired(now):
        reason = ChangeReason.EXPIRED
    elif not coupon.is_active(now):
        reason = ChangeReason.NOT_STARTED
    elif _is_used_up(coupon, cart.user):
        reason = ChangeReason.USED_UP
    else:
        return None

    change = CouponChange(
        old=coupon, new=find_replacement(coupon, cart, now=now), reason=reason
    )
    cart.coupon = change.new
    cart.coupon_notice = _notice_for(change, cart)
    cart.save(update_fields=["coupon", "coupon_notice"])
    return change


def _notice_for(change: CouponChange, cart: Cart) -> str:
    """The customer-facing explanation of a swap or removal."""
    old = change.old
    if change.reason is ChangeReason.EXPIRED:
        expired_on = timezone.localtime(old.expires_at)
        why = f"{old.code} expired on {expired_on:%b} {expired_on.day}"
    elif change.reason is ChangeReason.USED_UP:
        why = f"You've already used {old.code}, and it's one per customer"
    else:
        why = f"{old.code} isn't running right now"

    if change.new is None:
        return f"{why}, and no replacement is available right now."
    notice = f"{why}, so we applied {change.new.code} instead"
    discount = cart.discount()
    if discount:
        return f"{notice}, which saves you ${discount:,.2f} on this cart."
    return f"{notice}."


def find_replacement(
    coupon: Coupon, cart: Cart, *, now: datetime | None = None
) -> Coupon | None:
    """Choose the coupon that takes over from an expired ``coupon`` on ``cart``.

    1. Follow the staff-set ``replaced_by`` chain to the first coupon that
       is active and not used up by the cart's customer. A chain target is
       returned even if the cart is below its minimum — staff chose it, and
       it simply starts out paused. A loop in the chain ends the walk.
    2. Otherwise, among active public coupons whose minimum the cart meets
       and that the customer has not used up, pick the one whose savings on
       this cart are closest, in either direction, to what ``coupon`` would
       have saved.
    3. Ties go to the bigger saving, then to the most recently created.

    Returns ``None`` when nothing qualifies; the caller removes the coupon.
    """
    now = now or timezone.now()
    user = cart.user

    visited = {coupon.pk}
    candidate = coupon.replaced_by
    while candidate is not None and candidate.pk not in visited:
        visited.add(candidate.pk)
        if candidate.is_active(now) and not _is_used_up(candidate, user):
            return candidate
        candidate = candidate.replaced_by

    total = cart.total()
    target = coupon.savings_for(total)
    matches = [
        match
        for match in Coupon.objects.active(now).public().exclude(pk__in=visited)
        if match.meets_minimum(total) and not _is_used_up(match, user)
    ]
    if not matches:
        return None

    def closeness(match: Coupon) -> tuple:
        savings = match.savings_for(total)
        return (
            abs(savings - target),
            -savings,
            -match.created_at.timestamp(),
            -match.pk,
        )

    return min(matches, key=closeness)


def _is_used_up(coupon: Coupon, user: AbstractBaseUser) -> bool:
    """Whether a once-per-customer coupon has already been used by ``user``.

    Always ``False`` until ``Order.coupon`` exists (coupons plan, Phase 3).
    """
    return False
