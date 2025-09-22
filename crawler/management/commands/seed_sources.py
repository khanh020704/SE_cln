from django.core.management.base import BaseCommand
from sources.models import Source

FEEDS = [
    ("VnExpress - Tin mới", "https://vnexpress.net", "https://vnexpress.net/rss/tin-moi-nhat.rss"),
    ("Tuổi Trẻ - Mới nhất", "https://tuoitre.vn", "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
    ("Thanh Niên - Thời sự", "https://thanhnien.vn", "https://thanhnien.vn/rss/thoi-su.rss"),
    ("VietNamNet - Thời sự", "https://vietnamnet.vn", "https://vietnamnet.vn/rss/thoi-su.rss"),
    ("Dân Trí - Mới nhất", "https://dantri.com.vn", "https://dantri.com.vn/rss/home.rss"),
    ("VTV - Thời sự", "https://vtv.vn", "https://vtv.vn/trong-nuoc.rss"),
    ("VietnamPlus - Thời sự", "https://www.vietnamplus.vn", "https://www.vietnamplus.vn/rss/thoi-su.rss"),
]

class Command(BaseCommand):
    help = "Seed/cập nhật danh sách nguồn RSS"

    def handle(self, *args, **opts):
        n = 0
        for name, home, rss in FEEDS:
            _, created = Source.objects.update_or_create(
                name=name,
                defaults={"homepage": home, "rss_url": rss, "is_active": True, "source_score": 1.0}
            )
            n += int(created)
        self.stdout.write(self.style.SUCCESS(f"Upserted {n} new sources"))
