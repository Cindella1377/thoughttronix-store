from django.urls import path

from . import views

app_name = "wishlists"

urlpatterns = [
    path("wishlists/", views.WishlistIndexView.as_view(), name="index"),
    path("wishlists/<int:pk>/", views.WishlistDetailView.as_view(), name="detail"),
    path(
        "wishlists/<int:pk>/rename/",
        views.WishlistRenameView.as_view(),
        name="rename",
    ),
    path(
        "wishlists/<int:pk>/delete/",
        views.WishlistDeleteView.as_view(),
        name="delete",
    ),
    path("wishlists/<int:pk>/main/", views.MakeMainView.as_view(), name="make_main"),
    path(
        "wishlists/<int:pk>/share/",
        views.LinkSharingView.as_view(),
        name="link_sharing",
    ),
    path(
        "wishlists/<int:pk>/public/",
        views.PublicToggleView.as_view(),
        name="public_toggle",
    ),
    path(
        "wishlists/<int:pk>/items/<int:item_pk>/remove/",
        views.ItemRemoveView.as_view(),
        name="item_remove",
    ),
    path(
        "wishlists/<int:pk>/items/<int:item_pk>/<str:direction>/",
        views.ItemMoveView.as_view(),
        name="item_move",
    ),
    path(
        "wishlists/lamp/<int:product_pk>/",
        views.LampView.as_view(),
        name="lamp",
    ),
    path(
        "wishlists/shared/<str:token>/",
        views.SharedListView.as_view(),
        name="shared",
    ),
    path(
        "wishlists/save/<int:product_pk>/<int:pk>/",
        views.SaveToView.as_view(),
        name="save_to",
    ),
    # Singular, so a username can never collide with an owner path.
    path("wishlist/<str:username>/", views.PublicPageView.as_view(), name="public"),
]
