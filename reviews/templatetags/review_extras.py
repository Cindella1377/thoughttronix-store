from django import template

from ..models import Review
from ..views import form_place_context

register = template.Library()


@register.inclusion_tag("reviews/partials/_section.html", takes_context=True)
def reviews_section(context, product):
    """The product page's reviews: summary, the form's place, and the list.

    The viewer's own review sits in the form's place, pinned above the
    list, so the list leaves it out.
    """
    user = context["user"]
    reviews = product.reviews.select_related("author")
    if user.is_authenticated:
        reviews = reviews.exclude(author=user)
    return {
        **form_place_context(user, product),
        "user": user,
        "summary": Review.objects.summary(product),
        "reviews": reviews,
    }


@register.filter
def editable_by(review, user):
    """Whether ``user`` may edit or delete ``review``."""
    return review.can_edit(user)
