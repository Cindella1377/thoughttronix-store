"""The checkout form — the codebase's showcase of declarative validation.

Every rule is visible at its field declaration, in the style of data
annotations: field types validate (``EmailField``), field arguments
validate (``required``, ``max_length``, ``ChoiceField``), and the
``validators=[...]`` list carries the rest. No ``clean_*`` methods
and no ``clean()`` — none of its current rules need imperative validation.
"""

from decimal import Decimal

from django import forms
from django.core.validators import RegexValidator

from products.forms import StyledModelForm

from .models import Coupon, Order
from .validators import validate_card_number, validate_expiry

US_STATES = [
    ("AL", "Alabama"),
    ("AK", "Alaska"),
    ("AZ", "Arizona"),
    ("AR", "Arkansas"),
    ("CA", "California"),
    ("CO", "Colorado"),
    ("CT", "Connecticut"),
    ("DE", "Delaware"),
    ("DC", "District of Columbia"),
    ("FL", "Florida"),
    ("GA", "Georgia"),
    ("HI", "Hawaii"),
    ("ID", "Idaho"),
    ("IL", "Illinois"),
    ("IN", "Indiana"),
    ("IA", "Iowa"),
    ("KS", "Kansas"),
    ("KY", "Kentucky"),
    ("LA", "Louisiana"),
    ("ME", "Maine"),
    ("MD", "Maryland"),
    ("MA", "Massachusetts"),
    ("MI", "Michigan"),
    ("MN", "Minnesota"),
    ("MS", "Mississippi"),
    ("MO", "Missouri"),
    ("MT", "Montana"),
    ("NE", "Nebraska"),
    ("NV", "Nevada"),
    ("NH", "New Hampshire"),
    ("NJ", "New Jersey"),
    ("NM", "New Mexico"),
    ("NY", "New York"),
    ("NC", "North Carolina"),
    ("ND", "North Dakota"),
    ("OH", "Ohio"),
    ("OK", "Oklahoma"),
    ("OR", "Oregon"),
    ("PA", "Pennsylvania"),
    ("RI", "Rhode Island"),
    ("SC", "South Carolina"),
    ("SD", "South Dakota"),
    ("TN", "Tennessee"),
    ("TX", "Texas"),
    ("UT", "Utah"),
    ("VT", "Vermont"),
    ("VA", "Virginia"),
    ("WA", "Washington"),
    ("WV", "West Virginia"),
    ("WI", "Wisconsin"),
    ("WY", "Wyoming"),
]

zip_validator = RegexValidator(
    r"^\d{5}(-\d{4})?$", "Enter a ZIP code like 79016 or 79016-1234."
)
cvv_validator = RegexValidator(r"^\d{3,4}$", "Enter the 3- or 4-digit CVV.")


class CheckoutForm(forms.Form):
    """One page, one POST: contact, shipping, billing, payment."""

    email = forms.EmailField(label="Email")

    shipping_name = forms.CharField(label="Full name", max_length=100)
    shipping_street = forms.CharField(label="Street address", max_length=200)
    shipping_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    shipping_city = forms.CharField(label="City", max_length=100)
    shipping_state = forms.ChoiceField(label="State", choices=US_STATES)
    shipping_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    billing_name = forms.CharField(label="Full name", max_length=100)
    billing_street = forms.CharField(label="Street address", max_length=200)
    billing_line2 = forms.CharField(
        label="Apt, suite, etc. (optional)", max_length=200, required=False
    )
    billing_city = forms.CharField(label="City", max_length=100)
    billing_state = forms.ChoiceField(label="State", choices=US_STATES)
    billing_zip = forms.CharField(
        label="ZIP code", max_length=10, validators=[zip_validator]
    )

    card_number = forms.CharField(
        label="Card number", max_length=23, validators=[validate_card_number]
    )
    card_expiry = forms.CharField(
        label="Expiry (MM/YY)", max_length=5, validators=[validate_expiry]
    )
    card_cvv = forms.CharField(label="CVV", max_length=4, validators=[cvv_validator])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs["class"] = "select w-full"
            else:
                widget.attrs["class"] = "input w-full"

    # Field groups for the template — the form owns its own structure.

    def shipping_fields(self):
        return [self[name] for name in self.fields if name.startswith("shipping_")]

    def billing_fields(self):
        return [self[name] for name in self.fields if name.startswith("billing_")]

    def card_fields(self):
        return [self[name] for name in self.fields if name.startswith("card_")]


class CouponApplyForm(forms.Form):
    """The cart page's coupon box.

    Rejects only codes that don't exist or haven't started. An expired or
    used-up code is valid here on purpose: ``apply_coupon`` swaps it.
    """

    code = forms.CharField(
        label="Coupon code",
        max_length=30,
        widget=forms.TextInput(
            attrs={"class": "input join-item w-full", "placeholder": "Coupon code"}
        ),
    )

    def clean_code(self):
        code = Coupon.normalize_code(self.cleaned_data["code"])
        coupon = Coupon.objects.filter(code=code).first()
        if coupon is None:
            raise forms.ValidationError("We don't recognize that code.")
        if coupon.status() == Coupon.Status.SCHEDULED:
            raise forms.ValidationError(f"{code} isn't active yet — check back soon.")
        return code


DATETIME_LOCAL = "%Y-%m-%dT%H:%M"


class CouponForm(StyledModelForm):
    """The back-office coupon form.

    Codes are normalized before the model's uniqueness check, so ``fall10``
    collides with ``FALL10``. The cross-field rules — a percentage from 1
    to 100, an end after the start, and a replacement chain without loops —
    live in ``clean`` and ``clean_replaced_by``.
    """

    code = forms.CharField(
        max_length=30,
        validators=[
            RegexValidator(
                r"^[A-Za-z0-9-]+$", "Use letters, numbers, and hyphens only."
            )
        ],
    )
    value = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="A percentage (1–100) or a dollar amount, per the type above.",
    )
    minimum_order = forms.DecimalField(
        label="Minimum order (optional)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )

    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "value",
            "starts_at",
            "expires_at",
            "minimum_order",
            "once_per_customer",
            "is_public",
            "replaced_by",
        ]
        labels = {
            "starts_at": "Starts",
            "expires_at": "Expires",
            "once_per_customer": "Once per customer",
            "is_public": "Public",
            "replaced_by": "Replaced by (optional)",
        }
        help_texts = {
            "is_public": "May be offered automatically when another coupon expires.",
            "replaced_by": "When this coupon expires, carts holding it switch to "
            "this one.",
        }
        widgets = {
            "starts_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DATETIME_LOCAL
            ),
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"}, format=DATETIME_LOCAL
            ),
        }

    def clean_code(self):
        return Coupon.normalize_code(self.cleaned_data["code"])

    def clean_replaced_by(self):
        """Reject a replacement that is this coupon, or that leads back to it."""
        replacement = self.cleaned_data["replaced_by"]
        if replacement is None or self.instance.pk is None:
            return replacement  # A new coupon has nothing pointing at it yet.
        visited = set()
        link = replacement
        while link is not None and link.pk not in visited:
            if link.pk == self.instance.pk:
                if link == replacement:
                    raise forms.ValidationError("A coupon can't replace itself.")
                raise forms.ValidationError(
                    f"That makes a loop: {replacement.code} leads back to "
                    f"{self.instance.code}."
                )
            visited.add(link.pk)
            link = link.replaced_by
        return replacement

    def clean(self):
        cleaned = super().clean()
        percent = cleaned.get("discount_type") == Coupon.DiscountType.PERCENT
        value = cleaned.get("value")
        if percent and value is not None and not 1 <= value <= 100:
            self.add_error("value", "A percentage must be between 1 and 100.")
        starts_at, expires_at = cleaned.get("starts_at"), cleaned.get("expires_at")
        if starts_at and expires_at and expires_at <= starts_at:
            self.add_error("expires_at", "The end must come after the start.")
        return cleaned


class OrderStatusForm(forms.ModelForm):
    """The back-office status dropdown — any of the four states, anytime.

    Guarding the workflow (no un-cancelling, no re-shipping a delivered
    order) is deliberately left as a student exercise.
    """

    class Meta:
        model = Order
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "select"})}
