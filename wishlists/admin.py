from django.contrib import admin

from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    raw_id_fields = ("product",)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_main", "is_public", "is_sample")
    list_filter = ("is_main", "is_public", "is_sample")
    search_fields = ("name", "owner__username")
    inlines = [WishlistItemInline]
