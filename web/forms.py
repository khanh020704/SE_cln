# web/forms.py
import re
from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.validators import EmailValidator
from django.utils import timezone

from articles.models import Article
from sources.models import Category

UserModel = get_user_model()

PHONE_RE = re.compile(r"^(?:\+?84|0)(?:\d{9,10})$")


def normalize_identifier(x: str) -> str:
    return (x or "").strip().lower()


def is_phone(s: str) -> bool:
    return bool(PHONE_RE.fullmatch(s or ""))


# --------- Auth forms ----------
class RegisterForm(forms.Form):
    full_name = forms.CharField(label="Họ và tên", max_length=120)
    email_or_mobile = forms.CharField(label="Email hoặc SĐT", max_length=120)
    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, min_length=6)
    password2 = forms.CharField(label="Xác nhận mật khẩu", widget=forms.PasswordInput, min_length=6)

    def clean_email_or_mobile(self):
        v = normalize_identifier(self.cleaned_data["email_or_mobile"])
        if "@" in v:
            EmailValidator(message="Email không hợp lệ")(v)
        elif not is_phone(v):
            raise forms.ValidationError("SĐT không hợp lệ")
        if UserModel.objects.filter(username=v).exists():
            raise forms.ValidationError("Tài khoản đã tồn tại")
        return v

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "Mật khẩu xác nhận không khớp")
        return cleaned

    def save(self, request=None):
        data = self.cleaned_data
        username = data["email_or_mobile"]
        email = data["email_or_mobile"] if "@" in username else ""
        user = UserModel.objects.create_user(
            username=username, email=email, password=data["password1"]
        )
        user.first_name = data["full_name"][:30]
        user.save(update_fields=["first_name"])
        return user


class LoginForm(forms.Form):
    email_or_mobile = forms.CharField(label="Email hoặc SĐT")
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        ident = normalize_identifier(cleaned.get("email_or_mobile"))
        pwd = cleaned.get("password") or ""
        user = None
        if ident:
            user = authenticate(username=ident, password=pwd)
            if not user and "@" in ident:
                try:
                    u = UserModel.objects.get(email=ident)
                    user = authenticate(username=u.username, password=pwd)
                except UserModel.DoesNotExist:
                    pass
        if not user:
            raise forms.ValidationError("Sai thông tin đăng nhập")
        cleaned["user"] = user
        return cleaned


# --------- Guest comment form ----------
class GuestCommentForm(forms.Form):
    article_id = forms.IntegerField(widget=forms.HiddenInput)
    full_name = forms.CharField(label="Họ và tên", max_length=120)
    email = forms.EmailField(label="Email")
    content = forms.CharField(label="Nội dung", widget=forms.Textarea, min_length=3)


# --------- Article create/update form for journalists ----------
class ArticleCreateForm(forms.ModelForm):
    """
    Form đăng bài thủ công cho nhà báo.
    - Không yêu cầu source_url.
    - Có chọn categories (optional).
    - Luôn “bắt lỗi” nhẹ nhàng để không crash.
    """
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Chuyên mục"
    )

    class Meta:
        model = Article
        fields = [
            "title",
            "excerpt",
            "content_html",
            "main_image_url",
            "main_image_caption",
            "categories",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Tiêu đề"}),
            "excerpt": forms.Textarea(attrs={"rows": 3, "placeholder": "Tóm tắt ngắn…"}),
            "content_html": forms.Textarea(attrs={"rows": 12, "placeholder": "Nội dung (có thể chèn <img> …)"}),
            "main_image_url": forms.URLInput(attrs={"placeholder": "URL ảnh đại diện (tuỳ chọn)"}),
            "main_image_caption": forms.TextInput(attrs={"placeholder": "Chú thích ảnh (tuỳ chọn)"}),
        }
        labels = {
            "title": "Tiêu đề",
            "excerpt": "Tóm tắt",
            "content_html": "Nội dung",
            "main_image_url": "Ảnh đại diện (URL)",
            "main_image_caption": "Chú thích ảnh",
        }

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Tiêu đề không được để trống")
        return title

    def clean_content_html(self):
        content = (self.cleaned_data.get("content_html") or "").strip()
        if len(content) < 3:
            raise forms.ValidationError("Nội dung quá ngắn")
        return content

    def save(self, user, commit=True):
        """
        Lưu bài viết:
        - Gán author = user, origin = USER
        - source_url = None
        - published_at = now nếu chưa có
        """
        try:
            obj: Article = super().save(commit=False)
            obj.author = user
            obj.origin = Article.Origin.USER
            obj.source_url = None
            if not obj.published_at:
                obj.published_at = timezone.now()
            obj.is_visible = True
            if commit:
                obj.save()
                self.save_m2m()
            return obj
        except Exception as e:
            # biến lỗi thành ValidationError để view hiển thị đẹp
            raise forms.ValidationError(f"Lỗi lưu bài viết: {e}")

class ArticleForm(forms.ModelForm):
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={"class": "w-full", "size": 6})
    )

    class Meta:
        model = Article
        fields = [
            "title", "excerpt", "content_html",
            "main_image_url", "main_image_caption",
            "categories", "is_visible",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "w-full"}),
            "excerpt": forms.Textarea(attrs={"rows": 3, "class": "w-full"}),
            "content_html": forms.Textarea(attrs={"rows": 12, "class": "w-full monospace"}),
            "main_image_url": forms.URLInput(attrs={"class": "w-full"}),
            "main_image_caption": forms.TextInput(attrs={"class": "w-full"}),
        }

        def save(self, commit=True, author=None):
            obj = super().save(commit=False)
            # Bài do user đăng
            try:
                obj.origin = "user"
            except Exception:
                pass
            if author and getattr(obj, "author_id", None) is None:
                obj.author = author
            # Nếu không set published_at -> để None hoặc now() tuỳ bạn
            # ở đây: giữ nguyên giá trị form đã nhập; không ép now().
            if commit:
                obj.save()
                # ManyToMany
                try:
                    self.save_m2m()
                except Exception:
                    pass
            return obj
        
    # web/forms.py  (thêm/điều chỉnh nếu bạn đang đặt form ở đây)
from django import forms
from articles.models import Article
from sources.models import Category

class SubmitArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["title", "excerpt", "content_html", "main_image_url",
                  "main_image_caption", "categories", "is_visible"]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 3}),
            "content_html": forms.Textarea(attrs={"rows": 12}),
            "categories": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Gắn style/class 1 lần cho tất cả widget
        base_attrs = {
            "class": "w-full",
            "style": "width:100%;padding:12px 14px;border-radius:12px;"
                     "border:1px solid var(--ring);background:var(--card);"
                     "color:var(--text);outline:0",
        }
        for name, field in self.fields.items():
            current = field.widget.attrs
            current.update({k: v for k, v in base_attrs.items() if k not in current})
        # Label tiếng Việt
        self.fields["title"].label = "Tiêu đề"
        self.fields["excerpt"].label = "Tóm tắt"
        self.fields["content_html"].label = "Nội dung (có thể chèn ảnh)"
        self.fields["main_image_url"].label = "Ảnh đại diện (URL)"
        self.fields["main_image_caption"].label = "Chú thích ảnh đại diện"
        self.fields["categories"].label = "Chuyên mục"
        self.fields["is_visible"].label = "Hiển thị"

class ArticleSubmitFormSimple(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["title", "excerpt", "main_image_url", "content_html", "categories", "is_visible"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Tiêu đề…"}),
            "excerpt": forms.Textarea(attrs={"rows": 3, "placeholder": "Tóm tắt ngắn…"}),
            "main_image_url": forms.URLInput(attrs={"placeholder": "https://… (link ảnh trực tiếp .jpg/.png)"}),
            "content_html": forms.Textarea(attrs={"rows": 14, "placeholder": "Nội dung (có thể chèn <img src='...'>)…"}),
        }

    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all().order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 5})
    )


# web/forms.py
from django import forms
from django.utils.html import strip_tags
import re
from articles.models import Article

IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

class ArticleSubmitForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ["title", "excerpt", "main_image_url", "content_html", "categories", "is_visible"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "w-full", "placeholder": "Tiêu đề bài viết",
                "style": "width:100%;padding:12px;border-radius:12px;border:1px solid var(--ring);"
                         "background:var(--card);color:var(--text);outline:0"
            }),
            "excerpt": forms.Textarea(attrs={
                "class": "w-full", "rows": 3, "placeholder": "Tóm tắt ngắn",
                "style": "width:100%;padding:12px;border-radius:12px;border:1px solid var(--ring);"
                         "background:var(--card);color:var(--text);outline:0"
            }),
            "main_image_url": forms.URLInput(attrs={
                "class": "w-full", "id": "imgUrl", "placeholder": "URL ảnh tiêu đề (tùy chọn)",
                "style": "width:100%;padding:10px;border-radius:12px;border:1px solid var(--ring);"
                         "background:var(--card);color:var(--text);outline:0"
            }),
            "content_html": forms.Textarea(attrs={
                "class": "w-full mono", "rows": 16,
                "placeholder": 'Nội dung HTML sạch. Có thể chèn ảnh: <img src="https://...jpg">',
                "style": "width:100%;min-height:360px;padding:12px;border-radius:12px;"
                         "border:1px solid var(--ring);background:var(--card);color:var(--text);"
                         "outline:0;font-family:ui-monospace,monospace"
            }),
            "categories": forms.SelectMultiple(attrs={
                "class": "w-full",
                "style": "width:100%;padding:8px;border-radius:12px;border:1px solid var(--ring);"
                         "background:var(--card);color:var(--text);outline:0"
            }),
        }

    def clean_main_image_url(self):
        url = (self.cleaned_data.get("main_image_url") or "").strip()
        return url or ""

    def clean_content_html(self):
        html = self.cleaned_data.get("content_html") or ""
        # (Optional) very light guard so empty posts aren’t allowed
        if not strip_tags(html).strip():
            raise forms.ValidationError("Nội dung không được để trống.")
        return html

    def extract_first_image(self):
        """Return first <img src="..."> in content_html if any."""
        html = self.cleaned_data.get("content_html") or ""
        m = IMG_SRC_RE.search(html)
        return (m.group(1).strip() if m else "") or ""

