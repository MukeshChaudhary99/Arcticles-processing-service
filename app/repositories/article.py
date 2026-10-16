from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ARTICLE_STATUS_GROUP
from app.models.entities import Article, CodeMaster, Company, Tenant, TenantArticle


class ArticleRepository:
    """Tenant-scoped persistence; the service owns transaction boundaries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def tenant_exists(self, tenant_id: int) -> bool:
        return await self.session.get(Tenant, tenant_id) is not None

    async def list(
        self,
        tenant_id: int,
        limit: int,
        last_id: int | None,
        company_name: str | None,
        status: str | None,
    ):
        query = (
            select(Article, Company.name, CodeMaster.value)
            .join(TenantArticle, TenantArticle.article_id == Article.id)
            .join(Company, Company.id == Article.company_id)
            .join(CodeMaster, CodeMaster.id == Article.status_id)
            .where(TenantArticle.tenant_id == tenant_id, Company.tenant_id == tenant_id)
        )
        if last_id is not None:
            query = query.where(Article.id > last_id)
        if company_name is not None:
            query = query.where(Company.name == company_name)
        if status is not None:
            query = query.where(CodeMaster.value == status)
        return (
            await self.session.execute(query.order_by(Article.id).limit(limit))
        ).all()

    async def status_id(self, value: str) -> int | None:
        return await self.session.scalar(
            select(CodeMaster.id).where(
                CodeMaster.group_name == ARTICLE_STATUS_GROUP, CodeMaster.value == value
            )
        )

    async def add(self, tenant_id: int, article: Article) -> None:
        self.session.add(article)
        await self.session.flush()
        self.session.add(TenantArticle(tenant_id=tenant_id, article_id=article.id))
        await self.session.flush()


    async def get_pending_articles(
        self,
    ):
        query = (
            select(Article.title, Article.url, Company.name, Article.content)
            .join(CodeMaster, CodeMaster.id == Article.status_id)
        ).where(CodeMaster.value == "Pending")
        for article in (
            await self.session.execute(query.order_by(desc(Article.created_at)))
        ).all():
            yield article
    
    async def update_status(self, article_id: int, status_id: int) -> None:
        article = await self.session.get(Article, article_id)
        if article is not None:
            article.status_id = status_id
            await self.session.flush()

    async def get_article_by_id(self, article_id: int) -> Article | None:
        return await self.session.get(Article, article_id).with_for_update()