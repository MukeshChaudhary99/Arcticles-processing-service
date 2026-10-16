from sqlalchemy.exc import IntegrityError

from app.core.errors import ServiceError
from app.models.entities import Article
from app.repositories.article import ArticleRepository
from app.repositories.company import CompanyRepository
from app.schemas.article import ArticleCreate, ArticlePage, ArticleRead


class ArticleService:
    def __init__(self, repository: ArticleRepository, companies: CompanyRepository):
        self.repo = repository
        self.companies = companies

    @staticmethod
    def serialize(article: Article, company_name: str, status: str) -> ArticleRead:
        return ArticleRead(
            id=article.id,
            company_id=article.company_id,
            company_name=company_name,
            title=article.title,
            url=article.url,
            content=article.content,
            status=status,
            category=article.category,
            created_at=article.created_at,
            updated_at=article.updated_at,
        )

    async def require_tenant(self, tenant_id: int) -> None:
        if not await self.repo.tenant_exists(tenant_id):
            raise ServiceError(404, "Tenant not found")

    async def require_status(self, status: str) -> int:
        status_id = await self.repo.status_id(status)
        if status_id is None:
            raise ServiceError(422, "Unknown article status")
        return status_id

    async def create(self, payload: ArticleCreate) -> ArticleRead:
        tenant_id = payload.tenant_id
        try:
            async with self.repo.session.begin():
                status_id = await self.require_status(payload.status)
                company_id = await self.companies.get_or_create(
                    tenant_id, payload.company_name
                )
                article = Article(
                    **payload.model_dump(
                        exclude={"tenant_id", "company_name", "status", "url"}
                    ),
                    company_id=company_id,
                    url=str(payload.url),
                    status_id=status_id,
                )
                await self.repo.add(tenant_id, article)
                await self.repo.session.refresh(article)
                result = self.serialize(article, payload.company_name, payload.status)
            return result
        except IntegrityError as exc:
            # Only the URL uniqueness constraint is an expected client conflict.
            constraint = getattr(
                getattr(exc.orig, "__cause__", None), "constraint_name", None
            )
            if constraint == "uq_articles_url":
                raise ServiceError(
                    409, "An article with this URL already exists"
                ) from exc
            raise

    async def list(
        self,
        tenant_id: int,
        limit: int,
        last_id: int | None = None,
        company_name: str | None = None,
        status: str | None = None,
    ) -> ArticlePage:
        await self.require_tenant(tenant_id)
        if status is not None:
            await self.require_status(status)
        rows = await self.repo.list(tenant_id, limit + 1, last_id, company_name, status)
        items = [
            self.serialize(article, name, value)
            for article, name, value in rows[:limit]
        ]
        return ArticlePage(
            items=items,
            next_cursor=items[-1].id if len(rows) > limit else None,
        )
