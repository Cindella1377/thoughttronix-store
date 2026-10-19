from django import template

from ..forms import ReviewForm
from ..models import Review

register = template.Library()


@register.inclusion_tag("reviews/partials/_section.html", takes_context=True)
def reviews_section(context, product):
    """The product page's reviews: summary, the form's place, and the list."""
    user = context["user"]
    can_review = Review.objects.can_review(user, product)
    return {
        "product": product,
        "summary": Review.objects.summary(product),
        "form": ReviewForm(product=product, author=user) if can_review else None,
        "reviews": product.reviews.select_related("author"),
    }
