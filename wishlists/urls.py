from django.urls import path

from . import views

app_name = "wishlists"

urlpatterns = [
    path("wishlists/", views.WishlistIndexView.as_view(), name="index"),
    path("wishlists/<int:pk>/", views.WishlistDetailView.as_view(), name="detail"),
    path(
        "wishlists/<int:pk>/items/<int:item_pk>/remove/",
        views.ItemRemoveView.as_view(),
        name="item_remove",
    ),
    path(
        "wishlists/lamp/<int:product_pk>/",
        views.LampView.as_view(),
        name="lamp",
    ),
]
