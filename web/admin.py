# web/admin.py
from django.contrib import admin
from .models import Comment, Reaction

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "author", "email", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("author", "email", "content")

@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "article", "value", "session_key", "created_at")
    list_filter = ("value", "created_at")
