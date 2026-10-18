from django import forms
from django.core.exceptions import ValidationError

from .models import MAX_LISTS, Wishlist


class WishlistForm(forms.ModelForm):
    """Name a new list, or rename one.

    Names are unique per owner ignoring capitalisation; the database
    constraint is the backstop for anything past the form. An owner may
    keep at most ``MAX_LISTS`` lists.
    """

    class Meta:
        model = Wishlist
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input w-full", "placeholder": "Birthday"}
            )
        }

    def __init__(self, owner, *args, **kwargs):
        self.owner = owner
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        others = self.owner.wishlists.filter(name__iexact=name)
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise ValidationError("You already have a list with that name.")
        return name

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and self.owner.wishlists.count() >= MAX_LISTS:
            raise ValidationError(
                f"You already have {MAX_LISTS} lists — delete one to make room."
            )
        return cleaned

    def save(self, commit=True):
        if self.instance.pk:
            return super().save(commit)
        return Wishlist.objects.create_for(self.owner, self.cleaned_data["name"])
