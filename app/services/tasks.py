from app.services.article import ArticleService
from celery import shared_task
from celery_app import celery

@shared_task(name="tasks.pending_articles", bind=True, max_retries=3, default_retry_delay=60,retry_backoff=True, autoretry_for=(Exception,))
async def scheduled_check_pending_articles():
    article_service =  ArticleService(ArticleRepository(celery.db), CompanyRepository(celery.db))
    
    async for article in article_service.repo.get_pending_articles():
        await article_service._process_article(article)
    

@shared_task(name="tasks.process_article", bind=True, ack_late=True)
async def process_article_task(self, article_id: int):
    # facing confustion and unclearity with db injection in task
    article_service = ArticleService(ArticleRepository(self.db), CompanyRepository(self.db))
    await article_service._process_article(article_id)