# web/views.py
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

# Stdlib / third-party
import json

# Local apps
from articles.models import Article
from sources.models import Category
from web.models import Comment, Reaction

# web/views.py (thêm imports)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.shortcuts import redirect, render, get_object_or_404

from .forms import ArticleForm, SubmitArticleForm
from articles.models import Article

class ArticleDetailView(DetailView):
    model = Article
    template_name = "article_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    context_object_name = "a"

    def get_queryset(self):
        # vẫn giữ prefetch categories; comment/reactions chỉ prefetch khi có related_name tương ứng
        return (
            Article.objects.filter(is_visible=True)
            .prefetch_related("categories")
        )

    def get_context_data(self, **kwargs):
        from django.db.models import Q, Count

        ctx = super().get_context_data(**kwargs)
        a = self.object

        # ---- Reaction counts (trả về 'counts' để khớp template) ----
        try:
            from web.models import Reaction
            base = {k.label: 0 for k in Reaction.Kind}
            agg = Reaction.objects.filter(article=a).values("value").annotate(n=Count("id"))
            counts = base | {Reaction.Kind(r["value"]).label: r["n"] for r in agg}
        except Exception:
            counts = {"like": 0, "love": 0, "wow": 0, "sad": 0, "angry": 0}
        ctx["counts"] = counts

        # ---- Comments (nếu có model) ----
        try:
            from web.models import Comment
            ctx["comments"] = Comment.objects.filter(article=a).order_by("-created_at")
        except Exception:
            ctx["comments"] = []

        # ---- Related: CHỈ cùng category, exclude bài hiện tại, ưu tiên trùng nhiều category ----
        cat_ids = list(a.categories.values_list("id", flat=True))
        if cat_ids:
            related_qs = (
                Article.objects.filter(is_visible=True, categories__id__in=cat_ids)
                .exclude(pk=a.pk)
                .annotate(
                    same_cats=Count("categories", filter=Q(categories__id__in=cat_ids), distinct=True)
                )
                .order_by("-same_cats", "-published_at")
                .distinct()[:8]
            )
            ctx["related"] = list(related_qs)
        else:
            # Không có category -> không gợi ý để tránh lạc chủ đề
            ctx["related"] = []

        # Template đang dùng biến 'object' cho form comment
        ctx["object"] = a
        return ctx



def post_comment(request, article_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    a = get_object_or_404(Article, pk=article_id, is_visible=True)
    content = (request.POST.get("content") or "").strip()
    author = (request.POST.get("author") or "Ẩn danh").strip()[:120]
    if not content:
        return HttpResponseBadRequest("Empty content")

    Comment.objects.create(article=a, author=author, content=content)
    return redirect("article_detail", slug=a.slug)

def article_detail(request, slug):
    # Bài hiện tại
    a = get_object_or_404(
        Article.objects.select_related().prefetch_related('categories'),
        slug=slug, is_visible=True
    )

    # === RELATED: chỉ cùng category, exclude chính nó, distinct, ưu tiên trùng nhiều category ===
    cat_ids = list(a.categories.values_list('id', flat=True))
    if cat_ids:
        related_qs = (
            Article.objects.filter(is_visible=True)
            .exclude(pk=a.pk)
            .filter(categories__id__in=cat_ids)
            .annotate(
                same_cats=Count('categories', filter=Q(categories__id__in=cat_ids), distinct=True)
            )
            .order_by('-same_cats', '-published_at')
            .distinct()[:8]          # lấy tối đa 8 bài, KHÔNG filler khác chủ đề
        )
    else:
        # Không có category -> không gợi ý (tránh lạc chủ đề)
        related_qs = Article.objects.none()

    related = list(related_qs)

    # (Giữ nguyên phần reaction counts / comments của bạn)
    try:
        from django.db.models import Count as _Count  # tránh trùng tên
        from web.models import Reaction
        base = {k.label: 0 for k in Reaction.Kind}
        agg = Reaction.objects.filter(article=a).values('value').annotate(n=_Count('id'))
        counts = base | {Reaction.Kind(r['value']).label: r['n'] for r in agg}
    except Exception:
        counts = {"like": 0, "love": 0, "wow": 0, "sad": 0, "angry": 0}

    try:
        from web.models import Comment
        comments = Comment.objects.filter(article=a, is_approved=True).order_by('-created_at')
    except Exception:
        comments = []

    return render(request, 'article_detail.html', {
        'a': a,
        'related': related,
        'counts': counts,
        'comments': comments,
        'object': a,
    })



from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db.models import Count

from articles.models import Article
from .models import Reaction

@require_POST
@csrf_protect
def react_article(request):
    slug = request.POST.get('slug')
    raw  = request.POST.get('value')  # có thể là "like" hoặc "1"

    article = get_object_or_404(Article, slug=slug, is_visible=True)
    # map chuỗi -> số
    mapping = {
        'like':  Reaction.Kind.LIKE,
        'love':  Reaction.Kind.LOVE,
        'wow':   Reaction.Kind.WOW,
        'sad':   Reaction.Kind.SAD,
        'angry': Reaction.Kind.ANGRY,
    }
    try:
        kind = int(raw)
    except (TypeError, ValueError):
        kind = mapping.get(str(raw).lower())

    valid_values = {k.value for k in Reaction.Kind}
    if kind not in valid_values:
        return JsonResponse({'ok': False, 'error': 'invalid_reaction'}, status=400)

    # đảm bảo có session
    if not request.session.session_key:
        request.session.save()
    sk = request.session.session_key

    # toggle
    obj, created = Reaction.objects.get_or_create(
        article=article, session_key=sk, value=kind
    )
    if not created:
        obj.delete()
        toggled = False
    else:
        toggled = True

    # tổng hợp counts
    base = {k.label: 0 for k in Reaction.Kind}
    agg = Reaction.objects.filter(article=article).values('value').annotate(n=Count('id'))
    for r in agg:
        base[Reaction.Kind(r['value']).label] = r['n']

    return JsonResponse({'ok': True, 'toggled': toggled, 'counts': base})




def _qsearch(qs, q):
    if not q:
        return qs
    q = q.strip()
    # ưu tiên search_blob nếu có
    if "search_blob" in [f.name for f in Article._meta.get_fields()]:
        toks = [t for t in q.split() if t]
        for t in toks:
            qs = qs.filter(search_blob__icontains=t.lower())
        return qs
    return qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q))

import unicodedata, re

def normalize_query(q: str) -> str:
    """Bỏ dấu + lowercase + strip"""
    if not q:
        return ""
    try:
        q = unicodedata.normalize("NFKD", q)
        q = q.encode("ascii", "ignore").decode("utf-8")
    except Exception:
        pass
    return re.sub(r"\s+", " ", q).lower().strip()


# web/views.py (chỉ paste phần helper + 2 view list)

from django.db.models import Q
import unicodedata, logging

def _normalize_no_accent(s: str) -> str:
    try:
        return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("utf-8").lower().strip()
    except Exception:
        return (s or "").lower().strip()

def search_articles(qs, q: str):
    """
    Tìm kiếm:
    - Có search_blob: tách token đã bỏ dấu -> filter search_blob__icontains(token)
    - Không có search_blob: dùng query gốc (có dấu) -> filter title/excerpt
    Luôn bắt ngoại lệ để không vỡ trang.
    """
    if not q:
        return qs
    try:
        has_search_blob = any(f.name == "search_blob" for f in Article._meta.get_fields())
    except Exception:
        has_search_blob = False

    try:
        if has_search_blob:
            nq = _normalize_no_accent(q)
            toks = [t for t in nq.split() if t]
            for t in toks:
                qs = qs.filter(search_blob__icontains=t)
            return qs
        else:
            # Fallback: giữ nguyên dấu để SQLite/Postgres match đúng
            return qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q))
    except Exception as e:
        logging.exception("Search error: %s", e)
        return qs  # không lọc nếu có lỗi

# web/views.py (thêm import)
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.contrib import messages

from .forms import ArticleCreateForm, ArticleSubmitFormSimple
from articles.models import Article

# web/views.py  (only the affected views)

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib import messages

from articles.models import Article
from .forms import ArticleSubmitForm

# add near the top
from django.utils.text import slugify
import time

from crawler.utils import normalize_image_url
# web/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from articles.models import Article
from crawler.utils import normalize_image_url


@login_required
def submit_article(request):
    """
    Trang cho phép user đăng bài mới.
    Yêu cầu đã đăng nhập (login_required).
    """
    if request.method == "POST":
        form = SubmitArticleForm(request.POST)
        if form.is_valid():
            # Tạo article mới nhưng chưa commit để chỉnh field
            article = form.save(commit=False)
            article.author = request.user
            article.is_visible = True
            article.published_at = timezone.now()

            # Chuẩn hoá ảnh đại diện
            raw_url = form.cleaned_data.get("main_image_url")
            article.main_image_url = normalize_image_url(raw_url)

            # Lưu article
            article.save()

            # Nếu form có categories (M2M) thì phải save_m2m
            form.save_m2m()

            return redirect("my_articles")
    else:
        form = SubmitArticleForm()

    return render(request, "articles/submit.html", {"form": form})



@login_required
def my_articles(request):
    qs = Article.objects.filter(author=request.user).order_by("-created_at", "-id")
    return render(request, "articles/my_articles.html", {"articles": qs})

@login_required
def submit_article_edit(request, pk: int):
    obj = get_object_or_404(Article, pk=pk, author=request.user)
    if request.method == "POST":
        form = ArticleSubmitForm(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.main_image_url:
                auto = form.extract_first_image()
                if auto:
                    obj.main_image_url = auto
            obj.save()
            form.save_m2m()
            messages.success(request, "Đã cập nhật bài viết.")
            return redirect("my_articles")
    else:
        form = ArticleSubmitForm(instance=obj)
    return render(request, "articles/submit.html", {"form": form, "edit_mode": True})



@login_required
def submit_article_delete(request, pk: int):
    """
    Xóa bài do chính user đăng (templates: web/templates/confirm_delete.html)
    """
    a = get_object_or_404(Article, pk=pk, author=request.user)
    if request.method == "POST":
        a.delete()
        messages.success(request, "Đã xóa bài.")
        return redirect("my_articles")
    return render(request, "confirm_delete.html", {"object": a})



class HomeView(ListView):
    model = Article
    template_name = "home.html"
    paginate_by = 20

    def get_queryset(self):
        qs = Article.objects.filter(is_visible=True)
        q = self.request.GET.get("q")
        sort = self.request.GET.get("sort")

        # Tìm kiếm bỏ dấu
        if q:
            from django.db.models import Q
            from .views import normalize_query
            nq = normalize_query(q)
            qs = qs.filter(Q(search_blob__icontains=nq))

        # Sắp xếp theo dropdown
        if sort == "oldest":
            qs = qs.order_by("published_at")
        elif sort == "source":
            # cần select_related nếu có ForeignKey tới Source
            qs = qs.select_related().order_by("categories__name", "-published_at")
        else:  # default newest
            qs = qs.order_by("-published_at")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = Category.objects.all().order_by("name")[:50]
        ctx["q"] = self.request.GET.get("q", "")
        ctx["sort"] = self.request.GET.get("sort", "")
        return ctx
    
    


class CategoryView(ListView):
    template_name = "category.html"
    context_object_name = "articles"
    paginate_by = 12

    def dispatch(self, request, *args, **kwargs):
        self.cat = get_object_or_404(Category, slug=kwargs.get("slug"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Article.objects.filter(is_visible=True)
        # lọc theo category nếu có M2M, else fallback theo tên
        try:
            has_categories = any(f.many_to_many and f.name == "categories" for f in Article._meta.get_fields())
        except Exception:
            has_categories = False

        if has_categories:
            qs = qs.filter(categories=self.cat)
        else:
            qs = qs.filter(Q(title__icontains=self.cat.name) | Q(excerpt__icontains=self.cat.name))

        q = self.request.GET.get("q", "")
        qs = search_articles(qs, q)
        return qs.order_by("-published_at", "-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.cat
        ctx["categories"] = Category.objects.all().order_by("name")[:50]
        ctx["q"] = self.request.GET.get("q", "")
        return ctx



