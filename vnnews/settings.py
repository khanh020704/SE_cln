# vnnews/settings.py
from pathlib import Path
import os

# -------------------------------------------------
# Paths
# -------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -------------------------------------------------
# Core
# -------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# Nếu bạn test qua http://127.0.0.1:8000 hoặc http://localhost:8000
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# -------------------------------------------------
# Apps
# -------------------------------------------------
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "taggit",

    # Your apps
    "sources",
    "articles",
    "crawler",   # <<< thêm để Django load tasks + management commands
    "web",
]

# -------------------------------------------------
# Middleware
# -------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serve static (dev/prod)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "vnnews.urls"

# -------------------------------------------------
# Templates
# -------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Bạn đang để template trong web/templates; vẫn giữ APP_DIRS để template trong app khác cũng load được
        "DIRS": [BASE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "vnnews.wsgi.application"

# -------------------------------------------------
# Database (dev: SQLite)
# -------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        # Nếu chuyển Postgres sau này:
        # "USER": os.getenv("DB_USER", ""),
        # "PASSWORD": os.getenv("DB_PASSWORD", ""),
        # "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        # "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# -------------------------------------------------
# Internationalization
# -------------------------------------------------
LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------
# Static & Media
# -------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # dùng cho collectstatic (prod)
# Nếu bạn có thư mục static riêng (không bắt buộc):
STATICFILES_DIRS = [
    # BASE_DIR / "web" / "static",
]

# WhiteNoise nén + hash
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------
# Sessions & Cache (nhẹ nhàng cho dev)
# -------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "vnnews-locmem",
    }
}
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 ngày
SESSION_SAVE_EVERY_REQUEST = True

# -------------------------------------------------
# Celery
# -------------------------------------------------
# Dev khuyên dùng Redis (nếu bạn đang chạy Redis local như đã set up)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Dev: chạy thật (worker/beat) → ALWAYS_EAGER = False
# Nếu muốn test không cần worker, bạn có thể tạm bật eager = True
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_ALWAYS_EAGER", "0") == "1"
CELERY_TASK_EAGER_PROPAGATES = True

# -------------------------------------------------
# Logging (gọn nhẹ, dễ debug)
# -------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "crawler": {"handlers": ["console"], "level": "INFO"},
    },
}

# gửi email reset password ra console trong dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@vnnews.local"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
