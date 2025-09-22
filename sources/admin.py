# sources/admin.py
from django.contrib import admin
from .models import Category, Source

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    search_fields = ("name", "slug")
    list_filter = ("parent",)

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "rss_url", "last_crawled_at")
    list_filter = ("is_active",)
    search_fields = ("name", "rss_url")
