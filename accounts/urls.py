from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.AccountView.as_view(), name="account"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
    path(
        "password/change/",
        views.ChangePasswordView.as_view(),
        name="password_change",
    ),
    path(
        "password/reset/",
        views.ResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        views.ResetSentView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.ResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
