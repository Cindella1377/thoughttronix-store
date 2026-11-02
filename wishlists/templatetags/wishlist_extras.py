from django import template

from wishlists.models import Wishlist

register = template.Library()


@register.simple_tag
def lists_for(user, product):
    """The user's lists, each marked ``has_product`` for this product."""
    return Wishlist.objects.with_product_flag(user, product)
