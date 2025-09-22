from django.core.management.base import BaseCommand
from sources.models import Source
from crawler.tasks import _fetch_and_save_article
import feedparser

class Command(BaseCommand):
    help = "Crawl tất cả nguồn ngay (SYNC, bỏ qua giờ). Dùng để ép dữ liệu vào DB khi dev."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **opts):
        limit = opts["limit"]
        total = 0
        for src in Source.objects.filter(is_active=True, rss_url__isnull=False).exclude(rss_url=""):
            feed = feedparser.parse(src.rss_url)
            entries = feed.entries or []
            self.stdout.write(f"[SYNC] {src.name}: {len(entries)} entries")
            for e in entries[:limit]:
                url = e.get("link")
                if not url:
                    continue
                pub = e.get("published") or e.get("updated")
                _fetch_and_save_article(src.id, url, pub)  # chạy inline, không cần Celery
                total += 1
        self.stdout.write(self.style.SUCCESS(f"Done. fetched ~{total} entries"))
