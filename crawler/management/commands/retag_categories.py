# crawler/management/commands/retag_categories.py
from django.core.management.base import BaseCommand
from articles.models import Article
from crawler.tasks import _pick_category  # dùng lại hàm

class Command(BaseCommand):
    help = "Gắn Category tự động cho các bài chưa có"

    def handle(self, *args, **opts):
        n = 0
        for a in Article.objects.filter(category__isnull=True):
            cat = _pick_category(a.title or a.summary or a.content[:120])
            if cat:
                a.category = cat
                a.save(update_fields=["category"])
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Retagged: {n}"))
        if n == 0:
            self.stdout.write("No articles needed retagging.")
    