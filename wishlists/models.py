"""Wishlists: named lists of products a shopper wants to keep.

Every rule lives here — one main list per owner, names unique per owner
ignoring case, new items on top, a fresh share token each time link
sharing is turned on — so the views only look things up and render.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.functions import Lower

from products.models import Product

MAIN_LIST_NAME = "My Wishlist"
MAX_LISTS = 20


class WishlistManager(models.Manager):
    def main_for(self, user):
        """Return the user's main list, creating "My Wishlist" if they have none."""
        wishlist = self.filter(owner=user, is_main=True).first()
        if wishlist is None:
            wishlist = self.create(owner=user, name=MAIN_LIST_NAME, is_main=True)
        return wishlist

    def create_for(self, user, name):
        """Create a named list; a user's first list becomes their main list."""
        is_main = not self.filter(owner=user).exists()
        return self.create(owner=user, name=name, is_main=is_main)


class Wishlist(models.Model):
    """One of a user's named lists. Exactly one is starred as main."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlists",
    )
    name = models.CharField(max_length=50)
    is_main = models.BooleanField(default=False)
    # Set while "Share by link" is on; a new one each time it is turned on.
    share_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    is_public = models.BooleanField(default=False)
    # Made by the seed command, not chosen by the owner.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WishlistManager()

    class Meta:
        ordering = ["-is_main", Lower("name")]
        constraints = [
            models.UniqueConstraint(
                "owner",
                Lower("name"),
                name="unique_wishlist_name_per_owner",
                violation_error_message="You already have a list with that name.",
            ),
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(is_main=True),
                name="one_main_wishlist_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def delete(self, *args, **kwargs):
        # The lamp always needs somewhere to put things.
        if self.is_main:
            raise ValidationError("Star another list before deleting your main list.")
        return super().delete(*args, **kwargs)

    @transaction.atomic
    def make_main(self):
        """Star this list as main, unstarring the owner's other lists."""
        self.owner.wishlists.filter(is_main=True).exclude(pk=self.pk).update(
            is_main=False
        )
        self.is_main = True
        self.save(update_fields=["is_main"])

    def lines(self):
        """Items with their products loaded, top of the list first."""
        return self.items.select_related("product", "product__category")

    def products(self):
        """Products on this list, newest-placed first."""
        return Product.objects.filter(wishlist_items__wishlist=self).order_by(
            "-wishlist_items__position"
        )

    def has(self, product):
        return self.items.filter(product=product).exists()

    def add(self, product):
        """Put a product at the top of the list; a duplicate add does nothing.

        Callers decide whether the product may be added — the views refuse
        an unavailable one.
        """
        if self.has(product):
            return
        top = self.items.aggregate(top=models.Max("position"))["top"] or 0
        self.items.create(product=product, position=top + 1)

    def remove(self, product):
        self.items.filter(product=product).delete()

    def toggle(self, product):
        """Add the product, or remove it if it is already here.

        Returns True when the product was added.
        """
        if self.has(product):
            self.remove(product)
            return False
        self.add(product)
        return True


class WishlistItem(models.Model):
    """A product on a list. Higher ``position`` sits nearer the top."""

    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-position"]
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"],
                name="unique_product_per_wishlist",
            ),
        ]

    def __str__(self):
        return f"{self.product} on {self.wishlist}"
