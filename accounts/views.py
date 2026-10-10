from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView

from .forms import (
    ChangePasswordForm,
    EmailChangeForm,
    NewPasswordForm,
    ResetRequestForm,
    SignInForm,
    SignupForm,
)


class SignupView(SuccessMessageMixin, CreateView):
    """Create a customer account, then hand off to the login page.

    New users sign in themselves — auto-login after signup is left as a
    student exercise.
    """

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    success_message = "Account created — you can now sign in."


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SignInForm


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response


class ResetRequestView(PasswordResetView):
    """Ask for a reset link by email.

    Always hands off to the same "check your inbox" page, whether or not
    the address has an account.
    """

    template_name = "accounts/password_reset.html"
    form_class = ResetRequestForm
    subject_template_name = "accounts/email/password_reset_subject.txt"
    email_template_name = "accounts/email/password_reset_email.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class ResetSentView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class ResetConfirmView(SuccessMessageMixin, PasswordResetConfirmView):
    """Choose a new password from an emailed link, then sign in with it.

    A link that is expired, used, or malformed renders the same template
    with ``validlink`` false.
    """

    template_name = "accounts/password_reset_confirm.html"
    form_class = NewPasswordForm
    success_url = reverse_lazy("accounts:login")
    success_message = "Password changed — you can now sign in."


class AccountView(LoginRequiredMixin, SuccessMessageMixin, FormView):
    """The signed-in user's account page, which carries the change-email form."""

    template_name = "accounts/account.html"
    form_class = EmailChangeForm
    success_url = reverse_lazy("accounts:account")
    success_message = "Email changed."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    """Change a remembered password, then return to the account page.

    The stock view requires sign-in and keeps this session signed in
    while every other session for the account is signed out.
    """

    template_name = "accounts/password_change.html"
    form_class = ChangePasswordForm
    success_url = reverse_lazy("accounts:account")
    success_message = "Password changed."
