from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from products.models import Product

# Every cart field that changes when its coupon does.
COUPON_FIELDS = ["coupon", "coupon_notice", "replaced_coupon", "replaced_coupon_status"]


class Cart(models.Model):
    """A customer's cart — one per user, created lazily on first touch."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    coupon = models.ForeignKey(
        "Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="carts",
    )
    # Why the coupon last changed on its own — shown until dismissed.
    coupon_notice = models.TextField(blank=True)
    # The coupon the store swapped out, shown faded beside its replacement
    # until the customer changes the coupon themselves or checks out.
    replaced_coupon = models.ForeignKey(
        "Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # Why it was swapped out, as a short label: "Expired", "Already used".
    replaced_coupon_status = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    @classmethod
    def for_user(cls, user):
        """Return the user's cart, creating it on first touch."""
        cart, _ = cls.objects.get_or_create(user=user)
        return cart

    def add(self, product):
        """Add a product to the cart; a duplicate add increments its line."""
        item, created = self.items.get_or_create(product=product)
        if not created:
            item.quantity += 1
            item.save()
        return item

    def lines(self):
        """Line items with their products loaded, ready for display."""
        return self.items.select_related("product")

    def total(self):
        return sum((item.line_total for item in self.lines()), Decimal("0.00"))

    def item_count(self):
        """Total units across all lines — the navbar badge number."""
        return self.items.aggregate(count=models.Sum("quantity"))["count"] or 0

    # Coupon pricing assumes the coupon has been refreshed
    # (``orders.services.refresh_cart_coupon``); these methods never swap.

    def discount(self):
        """The coupon's savings, or zero if there is none or it is paused."""
        if self.coupon is None:
            return Decimal("0.00")
        total = self.total()
        if not self.coupon.meets_minimum(total):
            return Decimal("0.00")
        return self.coupon.savings_for(total)

    def grand_total(self):
        return self.total() - self.discount()

    def coupon_shortfall(self):
        """How much more the cart needs to reach its coupon's minimum."""
        if self.coupon is None or self.coupon.minimum_order is None:
            return Decimal("0.00")
        return max(Decimal("0.00"), self.coupon.minimum_order - self.total())

    def remove_coupon(self):
        self.coupon = None
        self.coupon_notice = ""
        self.replaced_coupon = None
        self.replaced_coupon_status = ""
        self.save(update_fields=COUPON_FIELDS)

    def dismiss_coupon_notice(self):
        self.coupon_notice = ""
        self.save(update_fields=["coupon_notice"])


class CartItem(models.Model):
    """One product line in a cart; the cart–product pair is unique."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"], name="unique_cart_product"
            )
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"

    @property
    def line_total(self):
        return self.product.price * self.quantity

    def increment(self):
        self.quantity += 1
        self.save()

    def decrement(self):
        """Step the quantity down, stopping at one — removal is explicit."""
        if self.quantity > 1:
            self.quantity -= 1
            self.save()


class Order(models.Model):
    """A placed order — a snapshot, never a live view of the catalog.

    Addresses are flat denormalized fields: the order must not change if
    the customer later edits anything. Of the card, only the last four
    digits survive checkout.
    """

    class Status(models.TextChoices):
        PLACED = "PLACED", "Placed"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PLACED
    )
    total = models.DecimalField(max_digits=10, decimal_places=2)
    email = models.EmailField()

    shipping_name = models.CharField(max_length=100)
    shipping_street = models.CharField(max_length=200)
    shipping_line2 = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=2)
    shipping_zip = models.CharField(max_length=10)

    billing_name = models.CharField(max_length=100)
    billing_street = models.CharField(max_length=200)
    billing_line2 = models.CharField(max_length=200, blank=True)
    billing_city = models.CharField(max_length=100)
    billing_state = models.CharField(max_length=2)
    billing_zip = models.CharField(max_length=10)

    card_last4 = models.CharField(max_length=4)

    # The coupon, snapshotted like everything else: code and discount stay
    # true to the purchase even if the coupon is later edited or deleted.
    # ``total`` is after the discount.
    coupon = models.ForeignKey(
        "Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    coupon_code = models.CharField(max_length=30, blank=True)
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    # default (not auto_now_add) so the seed can backdate orders.
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    @property
    def number(self):
        """The customer-facing order number, e.g. ``TT-2026-00042``."""
        return f"TT-{self.created_at.year}-{self.pk:05d}"


class OrderItem(models.Model):
    """One line of an order, priced as of purchase time.

    Name and unit price are denormalized: order history must not change
    when the catalog does. The product FK survives for linking while the
    product exists.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class CouponQuerySet(models.QuerySet):
    def active(self, now=None):
        """Coupons running at ``now``: started, and not yet expired."""
        now = now or timezone.now()
        return self.filter(starts_at__lte=now, expires_at__gt=now)

    def public(self):
        """Coupons the store may offer automatically as a replacement."""
        return self.filter(is_public=True)


class Coupon(models.Model):
    """A discount code, percent or fixed amount, live between two dates.

    Expiry is always computed from the dates, never stored: a coupon is
    active from ``starts_at`` up to, but not including, ``expires_at``.
    Codes are stored uppercase so they match case-insensitively.
    """

    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Percent off"
        AMOUNT = "AMOUNT", "Amount off"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"

    code = models.CharField(max_length=30, unique=True)
    discount_type = models.CharField(max_length=7, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    minimum_order = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    once_per_customer = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaces",
    )
    # default (not auto_now_add) so tests and the seed can set it.
    created_at = models.DateTimeField(default=timezone.now)

    objects = CouponQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.normalize_code(self.code)
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_code(code):
        """Codes match case-insensitively: stored and looked up uppercase."""
        return code.strip().upper()

    def is_active(self, now=None):
        now = now or timezone.now()
        return self.starts_at <= now < self.expires_at

    def is_expired(self, now=None):
        now = now or timezone.now()
        return now >= self.expires_at

    def status(self, now=None):
        """Scheduled, active, or expired at ``now`` — for the back office."""
        now = now or timezone.now()
        if now < self.starts_at:
            return self.Status.SCHEDULED
        if now < self.expires_at:
            return self.Status.ACTIVE
        return self.Status.EXPIRED

    @property
    def summary(self):
        """The discount in words: ``10% off`` or ``$5.00 off``."""
        if self.discount_type == self.DiscountType.PERCENT:
            return f"{self.value.normalize():f}% off"
        return f"${self.value:,.2f} off"

    def is_used_up_by(self, user):
        """Whether ``user`` has spent this once-per-customer coupon already."""
        return self.once_per_customer and self.orders.filter(user=user).exists()

    def meets_minimum(self, total):
        return self.minimum_order is None or total >= self.minimum_order

    def savings_for(self, total):
        """What this coupon takes off ``total``, capped so it never goes below zero."""
        if self.discount_type == self.DiscountType.PERCENT:
            savings = (total * self.value / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            savings = self.value
        return max(Decimal("0.00"), min(savings, total))
