# crawler/management/commands/crawl_recent.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import feedparser

from sources.models import Source
from crawler.tasks import task_fetch_feed, _fetch_and_save_article  # dùng lại logic có sẵn

class Command(BaseCommand):
    help = "Crawl các bài mới (RSS) trong khoảng giờ gần đây. Mặc định 4 giờ. " \
           "Dùng --sync để chạy đồng bộ (không cần Celery)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=4, help="Khoảng giờ gần đây (mặc định 4)")
        parser.add_argument("--sync", action="store_true", help="Chạy đồng bộ, không cần Celery worker")
        parser.add_argument("--limit", type=int, default=80, help="Giới hạn số entry mỗi feed (mặc định 80)")

    def handle(self, *args, **opts):
        hours = opts["hours"]
        sync = opts["sync"]
        limit = opts["limit"]

        since = timezone.now() - timedelta(hours=hours)
        self.stdout.write(self.style.NOTICE(f"Crawl recent since {since.isoformat()} "
                                            f"({'SYNC' if sync else 'ASYNC'})"))

        cnt_total = 0
        for src in Source.objects.filter(is_active=True, rss_url__isnull=False).exclude(rss_url=""):
            feed = feedparser.parse(src.rss_url)
            if not feed.entries:
                continue

            # Lọc entry theo thời gian nếu feed có published/updated
            entries = []
            for e in feed.entries[:limit]:
                ts = e.get("published") or e.get("updated")
                # nếu không có timestamp → cứ đưa vào; _fetch sẽ tự bỏ qua nếu nội dung quá ngắn
                if not ts:
                    entries.append(e)
                    continue
                try:
                    t = feedparser._parse_date(ts)
                except Exception:
                    t = None
                if t:
                    dt = timezone.datetime(*t[:6], tzinfo=timezone.utc)
                    if dt >= since:
                        entries.append(e)

            if not entries:
                continue

            if sync:
                # Không cần Celery worker — xử lý inline:
                self.stdout.write(f"  [SYNC] {src.name} - {len(entries)} entries")
                for e in entries:
                    url = e.get("link")
                    if not url:
                        continue
                    pub = e.get("published") or e.get("updated")
                    _fetch_and_save_article(src.id, url, pub)
                    cnt_total += 1
            else:
                # Dùng task có sẵn; cần Celery worker online
                self.stdout.write(f"  [ASYNC] queue feed: {src.name}")
                task_fetch_feed.delay(src.id)

        self.stdout.write(self.style.SUCCESS(f"Done. queued/fetched entries ~ {cnt_total}"))
