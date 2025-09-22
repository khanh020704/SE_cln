# articles/admin.py
from django.contrib import admin
from django.core.exceptions import FieldDoesNotExist
from .models import Article  # chỉ import Article của app articles

def has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except FieldDoesNotExist:
        return False

def is_m2m(model, name):
    try:
        f = model._meta.get_field(name)
        return f.many_to_many
    except FieldDoesNotExist:
        return False

# Xây list_display linh hoạt (ưu tiên các tên phổ biến)
_display_candidates = [
    "title", "headline", "name",
    "published_at", "created_at", "updated_at",
    "is_visible",
]
list_display = [f for f in _display_candidates if has_field(Article, f)]
# nếu vẫn trống, ít nhất hiển thị id
if not list_display:
    list_display = ["id"]

# list_filter chỉ nhận Field thực sự
_filter_candidates = ["is_visible", "published_at", "created_at", "updated_at"]
list_filter = [f for f in _filter_candidates if has_field(Article, f)]

# search_fields: tuỳ schema hiện có
_search_candidates = [
    "title", "headline", "name",
    "excerpt", "summary",
    "source_url", "url",
]
search_fields = [f for f in _search_candidates if has_field(Article, f)]

# readonly_fields: chỉ add khi có field
readonly_fields = [f for f in ["slug"] if has_field(Article, f)]

# filter_horizontal: chỉ áp dụng cho M2M có thật
filter_horizontal = [f for f in ["categories", "tags"] if is_m2m(Article, f)]

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = list_display
    list_filter = list_filter
    search_fields = search_fields
    readonly_fields = readonly_fields
    filter_horizontal = filter_horizontal
