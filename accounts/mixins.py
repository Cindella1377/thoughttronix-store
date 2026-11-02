"""Access-control mixins for the back office.

Per the PRD, back-office views gate on ``is_staff`` via mixins. Hiring
views gate on ``can_recruit`` instead, because candidate data is not for
all staff.
"""

from django.contrib.auth.mixins import UserPassesTestMixin


class StaffRequiredMixin(UserPassesTestMixin):
    """Allow staff only: anonymous users are redirected to the login
    page; signed-in non-staff get 403 (``AccessMixin``'s default split)."""

    def test_func(self):
        return self.request.user.is_staff


class RecruiterRequiredMixin(UserPassesTestMixin):
    """Allow those who can recruit, with the same split as above."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.can_recruit
