from django.contrib.auth.models import AbstractUser
from django.core.mail import send_mail
from django.db import models
from django.db.models.functions import Lower
from django.template.loader import render_to_string


class User(AbstractUser):
    """The store's user model.

    Roles use Django's own vocabulary: customers are plain users,
    employees are ``is_staff``, the admin is ``is_superuser``. One flag
    goes beyond it: ``is_recruiter`` opens hiring data to chosen staff.

    Every account has an email of its own: password reset finds the
    account by it, so no two accounts may share one, whatever the
    capitalisation.
    """

    # Required, unlike AbstractUser's optional email.
    email = models.EmailField("email address")
    # Nullable per the PRD: an absent job title is unknown, not empty.
    job_title = models.CharField(max_length=150, null=True, blank=True)  # noqa: DJ001
    # The one exception to Django's vocabulary: candidate data is not for
    # all staff. Read it through ``can_recruit``.
    is_recruiter = models.BooleanField(default=False)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_unique",
                violation_error_message="An account with this email already exists.",
            ),
        ]

    @property
    def display_name(self):
        """What other people see: the first name if set, else the username."""
        return self.first_name or self.username

    @property
    def can_recruit(self):
        """Whether this user may reach hiring data: the one place that decides."""
        return self.is_superuser or (self.is_staff and self.is_recruiter)

    def change_email(self, new_email):
        """Replace the account's email and tell the address it replaces.

        The one place an email changes: the old address is the owner's
        only warning if the change was not theirs. The notice does not
        say what the new address is.
        """
        old_email = self.email
        self.email = new_email
        self.save(update_fields=["email"])
        send_mail(
            subject=render_to_string(
                "accounts/email/email_changed_subject.txt"
            ).strip(),
            message=render_to_string(
                "accounts/email/email_changed_email.txt", {"user": self}
            ),
            from_email=None,
            recipient_list=[old_email],
        )
