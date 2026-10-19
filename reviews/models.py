"""Product reviews, rated in galaxies, from confirmed buyers only.

Every rule lives here — who may review, one review per customer per
product, how a product's reviews add up — so the views only look things
up and render.
"""

from enum import StrEnum

from django.conf import settings
from django.db import models
from django.utils import timezone

from orders.models import Order
from products.models import Product


class Eligibility(StrEnum):
    """Where a viewer stands with one product's reviews.

    The product page's form place switches on it; only ``CAN_REVIEW`` may
    post.
    """

    SIGNED_OUT = "signed_out"
    CAN_REVIEW = "can_review"
    HAS_REVIEWED = "has_reviewed"
    ON_ITS_WAY = "on_its_way"
    STAFF = "staff"
    NOT_A_BUYER = "not_a_buyer"


class ReviewManager(models.Manager):
    def eligibility(self, user, product):
        """Where ``user`` stands with reviewing ``product``.

        A confirmed buyer has a Delivered order containing the product.
        Staff are judged by their own orders: with a Delivered one they
        review like anyone else; without one they get ``STAFF``, whatever
        else they have ordered.
        """
        if not user.is_authenticated:
            return Eligibility.SIGNED_OUT
        if self.filter(author=user, product=product).exists():
            return Eligibility.HAS_REVIEWED
        statuses = set(
            Order.objects.filter(user=user, items__product=product).values_list(
                "status", flat=True
            )
        )
        if Order.Status.DELIVERED in statuses:
            return Eligibility.CAN_REVIEW
        if user.is_staff:
            return Eligibility.STAFF
        if statuses & {Order.Status.PLACED, Order.Status.SHIPPED}:
            return Eligibility.ON_ITS_WAY
        return Eligibility.NOT_A_BUYER

    def summary(self, product):
        """A product's galaxy average, review count, and galaxies to fill."""
        totals = self.filter(product=product).aggregate(
            average=models.Avg("rating"), count=models.Count("pk")
        )
        average = totals["average"]
        # Half a galaxy rounds up, the way a shopper reads 4.5.
        totals["filled"] = int(average + 0.5) if average is not None else 0
        return totals


class Review(models.Model):
    """One customer's galaxy rating of a product they received."""

    class Rating(models.IntegerChoices):
        BLACK_HOLE = 1, "Black hole"
        SPACE_JUNK = 2, "Space junk"
        LOW_ORBIT = 3, "Low orbit"
        STELLAR = 4, "Stellar"
        OUT_OF_THIS_WORLD = 5, "Out of this world"

        @property
        def tagline(self):
            """The line under a level's name; only Black hole has one."""
            if self == Review.Rating.BLACK_HOLE:
                return "it took something from me"
            return ""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(choices=Rating.choices)
    body = models.TextField(max_length=2000, blank=True)
    image = models.ImageField(upload_to="reviews/", blank=True)
    # default (not auto_now_add) so the seed can backdate reviews.
    created_at = models.DateTimeField(default=timezone.now)
    # Null until the first edit, so an unedited review shows no marker.
    updated_at = models.DateTimeField(null=True, blank=True)
    edited_by_staff = models.BooleanField(default=False)

    objects = ReviewManager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "author"],
                name="one_review_per_customer_per_product",
                violation_error_message="You've already reviewed this product.",
            ),
        ]

    def __str__(self):
        return f"{self.get_rating_display()} for {self.product} by {self.author}"
