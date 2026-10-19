"""Review views — thin per the architecture convention.

Every endpoint here is HTMX: it renders partials from
``templates/reviews/partials/``, never ``base.html``, and every write
also swaps the product's summary out-of-band.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View

from products.models import Product

from .forms import ReviewForm
from .models import Review


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

    Only a confirmed buyer may post — anyone else gets a 404. A form with
    errors comes back in place with everything the customer entered.
    """

    def post(self, request, product_pk):
        product = get_object_or_404(Product, pk=product_pk)
        if not Review.objects.is_confirmed_buyer(request.user, product):
            raise Http404("Reviews come from customers who've received this product.")
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
