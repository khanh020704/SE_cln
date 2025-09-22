# crawler/tasks.py
import datetime as dt
import feedparser, requests, bleach
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from trafilatura import fetch_url, extract
from trafilatura.metadata import extract_metadata
from readability import Document
from bs4 import BeautifulSoup
from django.utils.text import slugify

from sources.models import Source, Category
from articles.models import Article
from crawler.utils import fetch_and_extract  # lấy HTML sạch + blocks + figure/caption


HEADERS = {"User-Agent": "VNNewsBot/1.0 (+contact@example.com)"}

ALLOWED_TAGS = [
    "p","br","strong","b","em","i","a","ul","ol","li","blockquote","h2","h3","h4","img"
]
ALLOWED_ATTRS = {"a": ["href","title","rel","target"], "img": ["src","alt","title"]}


def _parse_datetime(s):
    if not s:
        return None
    try:
        t = feedparser._parse_date(s)
        if t:
            return dt.datetime(*t[:6])
    except Exception:
        pass
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _pick_category(title: str) -> Category | None:
    if not title:
        return Category.objects.order_by("id").first()
    t = title.lower()
    mapping = [
        (["bóng đá","thể thao","world cup","v-league"], "Thể thao"),
        (["kinh tế","tài chính","chứng khoán","doanh nghiệp","giá xăng"], "Kinh tế"),
        (["giáo dục","học sinh","thi tốt nghiệp","đại học"], "Giáo dục"),
        (["công nghệ","ai ","trí tuệ nhân tạo","iphone","android","mạng xã hội"], "Công nghệ"),
        (["chính phủ","quốc hội","bộ trưởng","thời sự"], "Thời sự"),
    ]
    for kws, catname in mapping:
        if any(kw in t for kw in kws):
            cat, _ = Category.objects.get_or_create(
                name=catname, defaults={"slug": slugify(catname)}
            )
            return cat
    return Category.objects.order_by("id").first()


def _extract_image_from_meta(html):
    try:
        soup = BeautifulSoup(html, "lxml")
        for prop in ["og:image", "twitter:image", "image"]:
            tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
            if tag and tag.get("content"):
                return tag["content"]
        first_img = soup.find("img")
        if first_img and first_img.get("src"):
            return first_img["src"]
    except Exception:
        pass
    return ""


def _sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def _fetch_and_save_article(source_id: int, url: str, published_str: str | None = None):
    src = Source.objects.get(pk=source_id)

    # fetch raw html
    html = fetch_url(url)
    if not html:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        html = r.text

    # readability
    try:
        doc = Document(html)
        main_html = doc.summary(html_partial=True)
        cleaned_html = _sanitize_html(main_html)
    except Exception:
        cleaned_html = ""

    # plain text
    text = extract(html, include_comments=False, include_links=False) or ""
    if len(text.strip()) < 300 and len(cleaned_html) < 300:
        return "too_short"

    # metadata
    meta = None
    try:
        meta = extract_metadata(html, url)
    except Exception:
        pass

    title = (getattr(meta, "title", None) or "").strip()
    description = (getattr(meta, "description", None) or "").strip()
    meta_image = (getattr(meta, "image", None) or "") or _extract_image_from_meta(html)

    pub_dt = _parse_datetime(published_str)
    if pub_dt and timezone.is_naive(pub_dt):
        pub_dt = timezone.make_aware(pub_dt, timezone.get_current_timezone())

    category = _pick_category(title or text[:120])

    parsed = fetch_and_extract(url)

    if parsed.get("content_html") and len(parsed["content_html"]) > len(cleaned_html):
        cleaned_html = parsed["content_html"]

    # create or update
    article, created = Article.objects.get_or_create(
        source_url=url,
        defaults=dict(
            title=(title[:500] if title else (parsed.get("title") or url)),
            content_html=cleaned_html or "",
            excerpt=(parsed.get("excerpt") or description or text[:300])[:800],
            main_image_url=(parsed.get("main_image_url") or meta_image or "")[:1000],
            main_image_caption=parsed.get("main_image_caption", ""),
            blocks=parsed.get("blocks") or {},
            published_at=pub_dt or timezone.now(),
            is_visible=True,
        ),
    )

    changed = []

    # update fields if better data available
    if cleaned_html and (not article.content_html or len(article.content_html) < len(cleaned_html)):
        article.content_html = cleaned_html
        changed.append("content_html")

    if not article.blocks and parsed.get("blocks"):
        article.blocks = parsed["blocks"]
        changed.append("blocks")

    best_img = parsed.get("main_image_url") or meta_image
    if best_img and not article.main_image_url:
        article.main_image_url = best_img[:1000]
        changed.append("main_image_url")

    if parsed.get("main_image_caption") and not article.main_image_caption:
        article.main_image_caption = parsed["main_image_caption"]
        changed.append("main_image_caption")

    if parsed.get("excerpt") and not article.excerpt:
        article.excerpt = parsed["excerpt"][:800]
        changed.append("excerpt")

    if not article.published_at and pub_dt:
        article.published_at = pub_dt
        changed.append("published_at")

    if hasattr(article, "categories") and category:
        if not article.categories.filter(pk=category.pk).exists():
            article.categories.add(category)

    if article.is_visible is False:
        article.is_visible = True
        changed.append("is_visible")

    if changed:
        article.save(update_fields=changed)

    return "created" if created else "updated"


@shared_task
def task_fetch_article(source_id: int, url: str, published_str: str | None = None):
    return _fetch_and_save_article(source_id, url, published_str)


@shared_task
def task_fetch_feed(source_id: int):
    src = Source.objects.get(pk=source_id)
    if not src.is_active or not src.rss_url:
        return 0
    feed = feedparser.parse(src.rss_url)
    count = 0
    for entry in feed.entries[:80]:
        url = entry.get("link")
        if not url:
            continue
        pub = entry.get("published") or entry.get("updated")
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            _fetch_and_save_article(src.id, url, pub)
        else:
            task_fetch_article.delay(src.id, url, pub)
        count += 1
    src.last_crawled_at = timezone.now()
    src.save(update_fields=["last_crawled_at"])
    return count


@shared_task
def schedule_all_sources():
    for s in Source.objects.filter(is_active=True):
        task_fetch_feed.delay(s.id)
