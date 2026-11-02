"""Main-list context for every page render.

The catalog draws a genie lamp on every thumbnail, gold when the product
is in the shopper's main list — one small query per authenticated request
supplies them all. It never creates a list.
"""

from .models import WishlistItem


def wishlist(request):
    if not request.user.is_authenticated:
        return {"wishlist_product_ids": set()}
    return {
        "wishlist_product_ids": set(
            WishlistItem.objects.filter(
                wishlist__owner=request.user, wishlist__is_main=True
            ).values_list("product_id", flat=True)
        )
    }
