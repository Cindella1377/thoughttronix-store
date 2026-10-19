from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path(
        "reviews/new/<int:product_pk>/",
        views.ReviewCreateView.as_view(),
        name="create",
    ),
]
