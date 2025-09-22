# crawler/management/commands/reindex_search.py
from django.core.management.base import BaseCommand
from articles.models import Article

class Command(BaseCommand):
    help = "Rebuild search_blob cho toàn bộ bài"

    def handle(self, *args, **opts):
        n = 0
        for a in Article.objects.all().iterator():
            # gọi save để rebuild search_blob
            a.save(update_fields=["search_blob"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Reindexed {n} articles"))
