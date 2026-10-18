"""Wishlist views — thin per the architecture convention.

Every owner view looks lists up through the signed-in user's own lists,
so someone else's list is a 404. HTMX endpoints render partials from
``templates/wishlists/partials/``, never ``base.html``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from products.models import Product

from .forms import WishlistForm
from .models import Wishlist, WishlistItem


def toggle_or_404(wishlist, product):
    """Toggle a product on a list; adding an unavailable product is a 404.

    The same not-for-sale semantics as add-to-cart: a product the store
    stopped selling can leave a list but never join one.
    """
    if not product.is_available and not wishlist.has(product):
        raise Http404("This product is not for sale.")
    return wishlist.toggle(product)


class OwnListsMixin(LoginRequiredMixin):
    """Restrict a list view to the signed-in user's own lists."""

    def get_queryset(self):
        return self.request.user.wishlists.all()


class OwnerFormMixin:
    """Hand the signed-in user to ``WishlistForm`` as the lists' owner."""

    form_class = WishlistForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class WishlistIndexView(
    LoginRequiredMixin, OwnerFormMixin, SuccessMessageMixin, CreateView
):
    """The owner's wishlists, with the new-list form."""

    template_name = "wishlists/index.html"
    success_url = reverse_lazy("wishlists:index")
    success_message = "Created “%(name)s”."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["wishlists"] = self.request.user.wishlists.annotate(
            item_count=Count("items")
        )
        return context


class WishlistRenameView(
    OwnListsMixin, OwnerFormMixin, SuccessMessageMixin, UpdateView
):
    template_name = "wishlists/rename.html"
    context_object_name = "wishlist"
    success_url = reverse_lazy("wishlists:index")
    success_message = "Renamed to “%(name)s”."


class MakeMainView(OwnListsMixin, SingleObjectMixin, View):
    """Star a list as main; the lamp adds to it from now on."""

    def post(self, request, pk):
        wishlist = self.get_object()
        wishlist.make_main()
        messages.success(request, f"“{wishlist.name}” is now your main list.")
        return redirect("wishlists:index")


class WishlistDeleteView(OwnListsMixin, DeleteView):
    """Confirm, then delete a list and its items. The main list is refused."""

    template_name = "wishlists/confirm_delete.html"
    context_object_name = "wishlist"
    success_url = reverse_lazy("wishlists:index")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.get_object().is_main:
            messages.error(request, "Star another list before deleting your main list.")
            return redirect("wishlists:index")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, f"Deleted “{self.object.name}”.")
        return super().form_valid(form)


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


def render_save_to(request, product):
    """Render the product page's wishlist controls, button and ticks together."""
    return render(request, "wishlists/partials/_save_to.html", {"product": product})


class LampView(LoginRequiredMixin, View):
    """HTMX: the genie lamp toggles a product in the main list.

    An add returns the gold lamp with its smoke puff; a remove returns the
    outline lamp without it. The product page's main button posts here
    too, with ``partial=save_to``, and gets its own controls back.
    """

    def post(self, request, product_pk):
        product = get_object_or_404(Product, pk=product_pk)
        added = toggle_or_404(Wishlist.objects.main_for(request.user), product)
        if request.POST.get("partial") == "save_to":
            return render_save_to(request, product)
        return render(
            request,
            "wishlists/partials/_lamp.html",
            {"product": product, "smoke": added},
        )


class SaveToView(LoginRequiredMixin, View):
    """HTMX: "Save to…" toggles a product in one of the owner's lists."""

    def post(self, request, product_pk, pk):
        product = get_object_or_404(Product, pk=product_pk)
        wishlist = get_object_or_404(request.user.wishlists, pk=pk)
        toggle_or_404(wishlist, product)
        return render_save_to(request, product)
