# sources/models.py
from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=150, unique=True)
    # Để tránh lỗi UNIQUE khi DB đã có dữ liệu cũ, cho phép null/không-unique trước
    slug = models.SlugField(max_length=160, unique=False, blank=True, null=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True, related_name='children', on_delete=models.CASCADE
    )
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ["parent__id", "name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:160]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.parent.name} › {self.name}" if self.parent else self.name


class Source(models.Model):
    name = models.CharField(max_length=200, unique=True)
    homepage = models.URLField(blank=True, null=True)
    rss_url = models.URLField(blank=True, null=True, db_index=True)
    is_active = models.BooleanField(default=True)
    source_score = models.FloatField(default=1.0)
    last_crawled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
