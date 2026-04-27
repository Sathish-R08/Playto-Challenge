import os
import sys

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Belt-and-suspenders: prefork/billiard on Windows often hits WinError 5; use solo unless overridden.
if sys.platform == "win32" and not os.environ.get("CELERY_WORKER_POOL"):
    pool = getattr(app.conf, "worker_pool", None) or getattr(app.conf, "pool", None)
    if pool in (None, "prefork", "processes", "default"):
        app.conf.worker_pool = "solo"
