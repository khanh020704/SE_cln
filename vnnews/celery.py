# vnnews/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vnnews.settings")

app = Celery("vnnews")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# chạy mỗi 2 tiếng, phút 0
app.conf.beat_schedule = {
    "crawl-every-2h": {
        "task": "crawler.tasks.schedule_all_sources",  # <- đã có trong crawler/tasks.py
        "schedule": crontab(minute=0, hour="*/2"),
    },
}

# (tuỳ chọn) đổi vị trí file lịch beat ra cùng root cho dễ thấy
app.conf.beat_schedule_filename = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "celerybeat-schedule.dat"
)
