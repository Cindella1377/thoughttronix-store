from django import forms
from django.core.exceptions import ValidationError

from .models import Review


class ReviewForm(forms.ModelForm):
    """A galaxy rating, required, and optional text up to 2,000 characters.

    One review per customer per product; the database constraint is the
    backstop for anything past the form. The template draws the rating
    as DaisyUI's rating component from ``levels``.
    """

    rating = forms.TypedChoiceField(
        choices=Review.Rating.choices,
        coerce=int,
        error_messages={"required": "Choose from one to five galaxies."},
    )

    class Meta:
        model = Review
        fields = ["rating", "body"]
        labels = {"body": "Your review (optional)"}
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "class": "textarea w-full",
                    "rows": 4,
                    "placeholder": "How did it go?",
                }
            )
        }

    def __init__(self, *args, product, author, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.product = product
        self.instance.author = author

    @property
    def levels(self):
        """Every galaxy level, for the picker and its names."""
        return list(Review.Rating)

    def clean(self):
        cleaned = super().clean()
        reviews = Review.objects.filter(
            product=self.instance.product, author=self.instance.author
        )
        if reviews.exclude(pk=self.instance.pk).exists():
            raise ValidationError("You've already reviewed this product.")
        return cleaned
