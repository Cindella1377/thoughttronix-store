"""Wishlist views — thin per the architecture convention.

Every owner view looks lists up through the signed-in user's own lists,
so someone else's list is a 404. HTMX endpoints render partials from
``templates/wishlists/partials/``, never ``base.html``.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import DetailView, TemplateView

from products.models import Product

from .models import Wishlist, WishlistItem


def toggle_or_404(wishlist, product):
    """Toggle a product on a list; adding an unavailable product is a 404.

    The same not-for-sale semantics as add-to-cart: a product the store
    stopped selling can leave a list but never join one.
    """
    if not product.is_available and not wishlist.has(product):
        raise Http404("This product is not for sale.")
    return wishlist.toggle(product)


class WishlistIndexView(LoginRequiredMixin, TemplateView):
    """The owner's wishlists."""

    template_name = "wishlists/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wishlists"] = self.request.user.wishlists.annotate(
            item_count=Count("items")
        )
        return context


class OwnListsMixin(LoginRequiredMixin):
    """Restrict a list view to the signed-in user's own lists."""

    def get_queryset(self):
        return self.request.user.wishlists.all()


class WishlistDetailView(OwnListsMixin, DetailView):
    """One of the owner's lists, with its controls."""

    template_name = "wishlists/detail.html"
    context_object_name = "wishlist"


def render_list_items(request, wishlist):
    """Render a list's items partial — the target of every item change."""
    return render(
        request,
        "wishlists/partials/_list_items.html",
        {"wishlist": wishlist, "editable": True},
    )


class ItemActionView(LoginRequiredMixin, View):
    """Base for HTMX item changes: act, then re-render the list's items.

    Items are always fetched through the owner's list — never by bare pk.
    """

    def post(self, request, pk, item_pk, **kwargs):
        item = get_object_or_404(
            WishlistItem.objects.select_related("wishlist"),
            pk=item_pk,
            wishlist__pk=pk,
            wishlist__owner=request.user,
        )
        self.act(item, **kwargs)
        return render_list_items(request, item.wishlist)

    def act(self, item, **kwargs):
        raise NotImplementedError


class ItemRemoveView(ItemActionView):
    def act(self, item):
        item.delete()


class LampView(LoginRequiredMixin, View):
    """HTMX: the genie lamp toggles a product in the main list.

    An add returns the gold lamp with its smoke puff; a remove returns the
    outline lamp without it.
    """

    def post(self, request, product_pk):
        product = get_object_or_404(Product, pk=product_pk)
        added = toggle_or_404(Wishlist.objects.main_for(request.user), product)
        return render(
            request,
            "wishlists/partials/_lamp.html",
            {"product": product, "smoke": added},
        )
