# articles/models.py
import re
import unicodedata
from html import unescape
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# -- Utils -------------------------------------------------
def _norm(s: str | None) -> str:
    """
    Normalize: bỏ dấu, lower, trim. Luôn bắt ngoại lệ để không crash.
    """
    if not s:
        return ""
    try:
        s = unicodedata.normalize("NFKD", s)
        s = s.encode("ascii", "ignore").decode("utf-8")
    except Exception:
        # bắt mọi ngoại lệ normalize để không crash
        s = s or ""
    return s.lower().strip()


_tag_re = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    """
    (Giữ lại để dùng nơi khác) Bóc HTML -> text thô.
    Không còn dùng cho search_blob theo yêu cầu mới.
    """
    if not html:
        return ""
    txt = unescape(html.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " "))
    txt = _tag_re.sub(" ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


# -- Models ------------------------------------------------
class Article(models.Model):
    class Origin(models.TextChoices):
        CRAWLER = "crawler", "Crawler"
        USER = "user", "User"

    title = models.CharField(max_length=500, blank=True, default="")
    slug = models.SlugField(max_length=520, blank=True, default="", db_index=True)

    # URL gốc (có thể trống cho bài đăng tay). Unique + NULL -> được phép nhiều NULL.
    source_url = models.URLField(unique=True, blank=True, null=True)

    excerpt = models.TextField(blank=True, default="")
    content_html = models.TextField(blank=True, default="")

    main_image_url = models.URLField(blank=True, default="")
    main_image_caption = models.CharField(max_length=500, blank=True, default="")

    blocks = models.JSONField(blank=True, null=True, default=dict)

    # Tác giả khi đăng tay; bài crawl thì để trống
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="articles",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    origin = models.CharField(max_length=16, choices=Origin.choices, default=Origin.CRAWLER)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(blank=True, null=True)

    is_visible = models.BooleanField(default=True)

    # DÙNG CHO SEARCH: chỉ chứa title + excerpt đã normalize
    search_blob = models.TextField(blank=True, default="")

    categories = models.ManyToManyField(
        "sources.Category", related_name="articles", blank=True
    )

    class Meta:
        ordering = ("-published_at", "-id")
        indexes = [
            models.Index(fields=["-published_at"], name="articles_pub_idx"),
            models.Index(fields=["is_visible", "-published_at"], name="articles_vis_pub_idx"),
        ]

    def __str__(self):
        return self.title or self.slug or f"Article#{self.pk}"

    def save(self, *args, **kwargs):
        # slug auto (không ép unique để tránh đổi URL cũ)
        try:
            if not self.slug and self.title:
                self.slug = slugify(self.title)[:520]
        except Exception:
            # giữ nguyên nếu slugify lỗi vì input lạ
            pass

        # Nếu có author mà chưa set origin -> coi là USER
        if self.author_id and not self.origin:
            self.origin = Article.Origin.USER

        # Nếu là bài người dùng đăng mà chưa có published_at -> gán now
        if self.origin == Article.Origin.USER and not self.published_at:
            try:
                self.published_at = timezone.now()
            except Exception:
                pass

        # build search_blob: CHỈ title + excerpt (không lấy content_html)
        try:
            title_part = self.title or ""
            excerpt_part = self.excerpt or ""
            self.search_blob = _norm(f"{title_part} {excerpt_part}")
        except Exception:
            if not self.search_blob:
                self.search_blob = ""

        return super().save(*args, **kwargs)
