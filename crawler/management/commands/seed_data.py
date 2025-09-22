# crawler/management/commands/seed_data.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from articles.models import Article
from sources.models import Category

LOREM = (
    "<p>Đây là nội dung mẫu để khởi tạo dữ liệu khi DB rỗng. "
    "Bạn có thể thay bằng nội dung thật khi crawler hoạt động.</p>"
)

SEED_CATEGORIES = [
    "Thời sự", "Công nghệ", "Kinh tế", "Giáo dục", "Thể thao"
]

SEED_ARTICLES = [
    {
        "title": "Tiêm kích Nhật lần đầu triển khai đến châu Âu trong hơn 70 năm",
        "source_url": "https://example.com/a/tiem-kich-nhat-lan-dau-trien-khai",
        "excerpt": "4 tiêm kích Nhật Bản đáp xuống châu Âu và Canada.",
    },
    {
        "title": "Thái Hòa: 'Tôi thương con trai khi đóng Tử chiến trên không'",
        "source_url": "https://example.com/a/thai-hoa-tu-chien-tren-khong",
        "excerpt": "Nghĩ về con trai 21 tuổi khi diễn cảnh sinh tử.",
    },
    {
        "title": "Giá nhà vượt xa khả năng chi trả của người mua",
        "source_url": "https://example.com/a/gia-nha-vuot-kha-nang-chi-tra",
        "excerpt": "Chênh lệch thu nhập và giá nhà tiếp tục nới rộng.",
    },
]

class Command(BaseCommand):
    help = "Seed categories và một vài bài viết mẫu để khởi tạo dữ liệu."

    def handle(self, *args, **options):
        # Tạo categories
        cat_map = {}
        for name in SEED_CATEGORIES:
            c, _ = Category.objects.get_or_create(name=name)
            cat_map[name] = c
        self.stdout.write(self.style.SUCCESS(f"Categories: {len(cat_map)}"))

        created = 0
        for idx, item in enumerate(SEED_ARTICLES, start=1):
            # tránh trùng bằng source_url (unique)
            if Article.objects.filter(source_url=item["source_url"]).exists():
                continue
            a = Article.objects.create(
                title=item["title"],
                source_url=item["source_url"],
                excerpt=item.get("excerpt", ""),
                content_html=item.get("content_html", LOREM),
                published_at=timezone.now(),
                is_visible=True,
            )
            # gán ngẫu nhiên 1-2 category
            a.categories.add(*list(cat_map.values())[:2])
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} articles"))
