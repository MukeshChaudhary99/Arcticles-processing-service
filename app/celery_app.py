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


from celery.signals import worker_process_init

@worker_process_init.connect()
def setup_db_connection(**kwargs):

    # ai suggeested to use async session for celery tasks, so we will create a new session factory for each worker process
    from app.db.session import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    # Create a new session factory for each worker process
    SessionLocal = sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    # Store the session factory in the Celery app's context
    celery.db = SessionLocal


# @workder_process_shutdown // close of db connection