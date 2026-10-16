from app.services.article import ArticleService
from celery import shared_task

@shared_task(name="tasks.pending_articles", bind=True, max_retries=3, default_retry_delay=60,retry_backoff=True)
async def scheduled_check_pending_articles(article_service: ArticleService):
    async for article in article_service.repo.get_pending_articles():
        await article_service._process_article(article)
    

@shared_task(name="tasks.process_article", bind=True, ack_late=True)
async def process_article_task(article_service: ArticleService, article_id: int):
    await article_service._process_article(article_id)