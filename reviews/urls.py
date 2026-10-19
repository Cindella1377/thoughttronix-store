from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path(
        "reviews/new/<int:product_pk>/",
        views.ReviewCreateView.as_view(),
        name="create",
    ),
    path("reviews/<int:pk>/", views.ReviewCardView.as_view(), name="card"),
    path("reviews/<int:pk>/edit/", views.ReviewEditView.as_view(), name="edit"),
    path(
        "reviews/<int:pk>/delete/",
        views.ReviewDeleteView.as_view(),
        name="confirm_delete",
    ),
]
