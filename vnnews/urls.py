# vnnews/urls.py
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

# Views
from web.views import (
    HomeView,
    CategoryView,
    ArticleDetailView,
    post_comment,
    react_article,            # API reactions
    submit_article,           # Trang tạo mới bài (user đăng)
    submit_article_edit,      # Sửa bài của tôi
    my_articles,              # Danh sách bài của tôi
    submit_article_delete,    # Xóa bài
)

from web import views_auth    # API/Pages auth

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Trang chính / danh mục / chi tiết
    path("", HomeView.as_view(), name="home"),
    path("c/<slug:slug>/", CategoryView.as_view(), name="category"),
    path("article/<slug:slug>/", ArticleDetailView.as_view(), name="article_detail"),

    # Đăng bài (yêu cầu đăng nhập)
    path("submit/", submit_article, name="submit_article"),
    path("me/articles/", my_articles, name="my_articles"),
    path("submit/<int:pk>/edit/", submit_article_edit, name="submit_article_edit"),
    path("submit/<int:pk>/delete/", submit_article_delete, name="submit_article_delete"),

    # APIs comment & reaction
    path("api/comment/<int:article_id>/", post_comment, name="post_comment"),
    path("api/react/", react_article, name="api_react"),  # Đặt 1 route duy nhất

    # Auth PAGES (cho các template {% url 'login' %}, {% url 'register' %}, {% url 'logout' %})
    path("auth/login/", views_auth.page_login, name="login"),
    path("auth/register/", views_auth.page_register, name="register"),
    path("auth/logout/", views_auth.page_logout, name="logout"),

    # Auth APIs (nếu có dùng AJAX)
    path("auth/api/register/", views_auth.api_register, name="api_register"),
    path("auth/api/login/", views_auth.api_login, name="api_login"),
    path("auth/api/guest-comment/", views_auth.api_guest_comment, name="api_guest_comment"),

    # Password reset (tuỳ chọn)
    path("auth/password-reset/", views_auth.ForgotPasswordView.as_view(), name="password_reset"),
    path(
        "auth/password-reset/done/",
        TemplateView.as_view(template_name="auth/password_reset_done.html"),
        name="password_reset_done",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
