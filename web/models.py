# web/models.py
from django.db import models
from django.utils import timezone
from django.conf import settings
from articles.models import Article

class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    author  = models.CharField(max_length=120, blank=True, default="")
    email   = models.EmailField(blank=True, default="")
    content = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author}: {self.content[:30]}"



class Reaction(models.Model):
    class Kind(models.IntegerChoices):
        LIKE  = 1, 'like'
        LOVE  = 2, 'love'
        WOW   = 3, 'wow'
        SAD   = 4, 'sad'
        ANGRY = 5, 'angry'

    article = models.ForeignKey('articles.Article', on_delete=models.CASCADE, related_name='reactions')
    value   = models.PositiveSmallIntegerField(choices=Kind.choices)
    session_key = models.CharField(max_length=40, db_index=True)  # nhận diện người dùng theo session
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['article', 'session_key', 'value'],
                name='uniq_reaction_per_session_kind'
            )
        ]

    def __str__(self):
        return f'{self.article_id}:{self.get_value_display()}:{self.session_key}'

