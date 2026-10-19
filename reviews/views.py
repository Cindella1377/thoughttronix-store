"""Review views — thin per the architecture convention.

Every endpoint here is HTMX: it renders partials from
``templates/reviews/partials/``, never ``base.html``, and every write
also swaps the product's summary out-of-band. A review the viewer may
not edit is a 404 from every one of its endpoints.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View

from products.models import Product

from .forms import ReviewForm
from .models import Eligibility, Review


def form_place_context(user, product):
    """What the form's place shows ``user``: the form, their card, or a message."""
    eligibility = Review.objects.eligibility(user, product)
    context = {"product": product, "eligibility": eligibility}
    if eligibility == Eligibility.CAN_REVIEW:
        context["form"] = ReviewForm(product=product, author=user)
    elif eligibility == Eligibility.HAS_REVIEWED:
        context["own_review"] = product.reviews.select_related("author").get(
            author=user
        )
    return context


def render_with_summary(request, template, context, product):
    """Render a partial, followed by the product's summary swapped out-of-band."""
    summary = render_to_string(
        "reviews/partials/_summary.html",
        {"summary": Review.objects.summary(product), "oob": True},
        request,
    )
    return HttpResponse(render_to_string(template, context, request) + summary)


class ReviewCreateView(LoginRequiredMixin, View):
    """HTMX: post a review; the form becomes the new card.

    Only a viewer who ``CAN_REVIEW`` may post — anyone else gets a 404. A
    form with errors comes back in place with everything the customer
    entered.
    """

    def post(self, request, product_pk):
        product = get_object_or_404(Product, pk=product_pk)
        eligibility = Review.objects.eligibility(request.user, product)
        if eligibility != Eligibility.CAN_REVIEW:
            raise Http404("You can't review this product.")
        form = ReviewForm(request.POST, product=product, author=request.user)
        if not form.is_valid():
            return render(
                request,
                "reviews/partials/_form.html",
                {"form": form, "product": product},
            )
        review = form.save()
        return render_with_summary(
            request, "reviews/partials/_card.html", {"review": review}, product
        )


class EditableReviewMixin:
    """Look the review up by pk; one the viewer may not edit is a 404."""

    def get_review(self):
        review = get_object_or_404(
            Review.objects.select_related("author", "product"), pk=self.kwargs["pk"]
        )
        if not review.can_edit(self.request.user):
            raise Http404("No such review.")
        return review


class ReviewCardView(EditableReviewMixin, View):
    """HTMX: one card, unchanged — for Cancel and Keep it."""

    def get(self, request, pk):
        return render(
            request, "reviews/partials/_card.html", {"review": self.get_review()}
        )


class ReviewEditView(EditableReviewMixin, View):
    """HTMX: the card becomes the form in place; saving turns it back."""

    def get(self, request, pk):
        review = self.get_review()
        form = ReviewForm(instance=review, product=review.product, author=review.author)
        return self.render_form(form)

    def post(self, request, pk):
        review = self.get_review()
        form = ReviewForm(
            request.POST, instance=review, product=review.product, author=review.author
        )
        if not form.is_valid():
            return self.render_form(form)
        review = form.save(commit=False)
        review.mark_edited()
        review.save()
        return render_with_summary(
            request, "reviews/partials/_card.html", {"review": review}, review.product
        )

    def render_form(self, form):
        return render(
            self.request,
            "reviews/partials/_form.html",
            {"form": form, "product": form.instance.product},
        )


class ReviewDeleteView(EditableReviewMixin, View):
    """HTMX: the card's buttons become an inline confirm; Yes deletes.

    Deleting re-renders the form's place, where the author's card sat, so
    the author can review again.
    """

    def get(self, request, pk):
        return render(
            request,
            "reviews/partials/_confirm_delete.html",
            {"review": self.get_review()},
        )

    def post(self, request, pk):
        review = self.get_review()
        product = review.product
        review.delete()
        return render_with_summary(
            request,
            "reviews/partials/_form_place.html",
            form_place_context(request.user, product),
            product,
        )
