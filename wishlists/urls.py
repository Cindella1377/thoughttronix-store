from django.urls import path

from . import views

app_name = "wishlists"

urlpatterns = [
    path("wishlists/", views.WishlistIndexView.as_view(), name="index"),
    path(
        "wishlists/lamp/<int:product_pk>/",
        views.LampView.as_view(),
        name="lamp",
    ),
]
