from celery import Celery
from app.core import constants
celery = Celery(
    "article_processor",
    broker=constants.CELERY_BROKER_URL,
    backend=constants.CELERY_RESULT_BACKEND,
)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    timezone=constants.CELERY_TIMEZONE,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    beat_schedule={
    “run-pending-articles”: {
    “task”: “tasks.pending_articles",
    “schedule”: 30.0
    }}
)