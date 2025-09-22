# crawler/management/commands/crawl_once.py
from django.core.management.base import BaseCommand, CommandError
from articles.models import Article
from sources.models import Category
from taggit.utils import parse_tags
from crawler.utils import fetch_and_extract
from django.utils.text import slugify

class Command(BaseCommand):
    help = "Crawl 1 bài báo từ URL và lưu với category/tag (tùy chọn)."

    def add_arguments(self, parser):
        parser.add_argument("url", type=str)
        parser.add_argument("--categories", type=str, help="VD: 'Thể thao, Bóng đá'")
        parser.add_argument("--tags", type=str, help="VD: 'V-League,SEA Games'")

    def handle(self, *args, **opts):
        url = opts["url"]
        self.stdout.write(self.style.WARNING(f"Crawling: {url}"))
        data = fetch_and_extract(url)

        art = Article.objects.create(
            source_url=url,
            title=data["title"],
            excerpt=data["excerpt"],
            content_html=data["content_html"],
            blocks=data["blocks"],
            main_image_url=data["main_image_url"],
            main_image_caption=data["main_image_caption"],
            search_blob=f"{data['title']} {data['excerpt']}"
        )

        if opts.get("categories"):
            for raw in parse_tags(opts["categories"]):
                cat, _ = Category.objects.get_or_create(name=raw, defaults={"slug": slugify(raw)})
                art.categories.add(cat)

        if opts.get("tags"):
            art.tags.add(*parse_tags(opts["tags"]))

        art.save()
        self.stdout.write(self.style.SUCCESS(f"Saved article #{art.id}: {art.title}"))
