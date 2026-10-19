"""Product reviews, rated in galaxies, from confirmed buyers only.

Every rule lives here — who may review, one review per customer per
product, how a product's reviews add up — so the views only look things
up and render.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from orders.models import Order
from products.models import Product


class ReviewManager(models.Manager):
    def is_confirmed_buyer(self, user, product):
        """Whether ``user`` has a Delivered order containing ``product``."""
        return (
            user.is_authenticated
            and Order.objects.filter(
                user=user, status=Order.Status.DELIVERED, items__product=product
            ).exists()
        )

    def can_review(self, user, product):
        """Whether ``user`` may write a review of ``product`` now."""
        return (
            self.is_confirmed_buyer(user, product)
            and not self.filter(author=user, product=product).exists()
        )

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
