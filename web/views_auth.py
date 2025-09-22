# web/views_auth.py
from __future__ import annotations

import re
from typing import Dict, Any

from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView
from django.http import JsonResponse, HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from articles.models import Article
from web.models import Comment
from .forms import RegisterForm, LoginForm


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
_phone_re = re.compile(r"^(?:\+?84|0)\d{9,10}$")
_email_re = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", re.I)


def _json_ok(payload: Dict[str, Any] | None = None, status: int = 200) -> JsonResponse:
    data = {"ok": True}
    if payload:
        data.update(payload)
    return JsonResponse(data, status=status)


def _json_err(errors: Dict[str, Any] | None = None, status: int = 400) -> JsonResponse:
    return JsonResponse({"ok": False, "errors": errors or {"__all__": ["Error"]}}, status=status)


# ---------------------------------------------------------------------
# Page views (form HTML)
# ---------------------------------------------------------------------
def page_login(request: HttpRequest):
    """Trang đăng nhập (HTML form)."""
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.cleaned_data["user"]
        auth_login(request, user)
        return redirect(request.GET.get("next") or reverse("home"))

    return render(request, "auth/login.html", {"form": form})


def page_register(request: HttpRequest):
    """Trang đăng ký (HTML form)."""
    if request.user.is_authenticated:
        return redirect("home")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(request)
        auth_login(request, user)
        return redirect("home")

    return render(request, "auth/register.html", {"form": form})


def page_logout(request: HttpRequest):
    """Đăng xuất và quay về trang chủ."""
    auth_logout(request)
    return redirect("home")


# ---------------------------------------------------------------------
# API endpoints (AJAX/JSON)
# ---------------------------------------------------------------------
@require_POST
@csrf_protect
def api_register(request: HttpRequest):
    """
    API đăng ký: full_name, email_or_mobile, password1, password2.
    Trả JSON: { ok, errors? }.
    """
    try:
        form = RegisterForm(request.POST)
        if not form.is_valid():
            return _json_err(form.errors, status=400)
        user = form.save(request)
        auth_login(request, user)
        return _json_ok()
    except Exception as e:  # luôn chặn để không crash
        return _json_err({"__all__": [str(e) or "Register error"]}, status=500)


@require_POST
@csrf_protect
def api_login(request: HttpRequest):
    """
    API đăng nhập: email_or_mobile + password.
    Trả JSON: { ok, errors? }.
    """
    try:
        form = LoginForm(request.POST)
        if not form.is_valid():
            return _json_err(form.errors, status=400)
        user = form.cleaned_data["user"]
        auth_login(request, user)
        return _json_ok()
    except Exception as e:
        return _json_err({"__all__": [str(e) or "Login error"]}, status=500)


@require_POST
@csrf_protect
def api_guest_comment(request: HttpRequest):
    """
    API bình luận không cần đăng nhập.
    Bắt buộc:
      - full_name (>=2)
      - email (email hợp lệ hoặc SĐT VN)
      - content (>=3)
      - article_id
    """
    try:
        full_name = (request.POST.get("full_name") or "").strip()
        email_or_phone = (request.POST.get("email") or "").strip().lower()
        content = (request.POST.get("content") or "").strip()
        article_id = request.POST.get("article_id")

        # Validate
        if len(full_name) < 2:
            return _json_err({"full_name": ["Tên quá ngắn"]}, status=400)
        if not (_phone_re.fullmatch(email_or_phone) or _email_re.fullmatch(email_or_phone)):
            return _json_err({"email": ["Email/SĐT không hợp lệ"]}, status=400)
        if len(content) < 3:
            return _json_err({"content": ["Nội dung quá ngắn"]}, status=400)

        article = get_object_or_404(Article, pk=article_id, is_visible=True)

        cmt = Comment.objects.create(
            article=article,
            author=full_name[:120],
            email=email_or_phone,
            content=content,
            is_approved=True,  # đổi False nếu muốn duyệt trước
        )

        return _json_ok(
            {
                "comment": {
                    "author": cmt.author or "Ẩn danh",
                    "email": cmt.email,
                    "content": cmt.content,
                    "created_at": cmt.created_at.strftime("%H:%M %d/%m/%Y"),
                }
            }
        )
    except Exception as e:
        return _json_err({"__all__": [str(e) or "Comment error"]}, status=500)


# ---------------------------------------------------------------------
# Forgot password page
# ---------------------------------------------------------------------
class ForgotPasswordView(PasswordResetView):
    """
    Trang 'Quên mật khẩu?'
    (Dev mặc định dùng EMAIL_BACKEND console/locmem — xem settings.)
    """
    form_class = PasswordResetForm
    template_name = "auth/password_reset_form.html"
    email_template_name = "auth/password_reset_email.txt"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
