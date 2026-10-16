from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers.dependencies import get_article_service, resolve_tenant
from app.schemas.article import ArticleCreate, ArticlePage, ArticleRead, Name, Status
from app.services.article import ArticleService

router = APIRouter(prefix="/articles", tags=["articles"])
TenantID = Annotated[int, Depends(resolve_tenant)]
Service = Annotated[ArticleService, Depends(get_article_service)]


@router.post("", response_model=ArticleRead, status_code=201)
async def create_article(payload: ArticleCreate, service: Service) -> ArticleRead:
    return await service.create(payload)


@router.get("", response_model=ArticlePage)
async def list_articles(
    tenant_id: TenantID,
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    last_id: Annotated[int | None, Query(gt=0, le=2_147_483_647)] = None,
    company_name: Annotated[Name | None, Query()] = None,
    status: Annotated[Status | None, Query()] = None,
) -> ArticlePage:
    return await service.list(tenant_id, limit, last_id, company_name, status)

@rounter.post("/process", status_code=202)
async def process_article(
    service: Service,
    article_id: Annotated[int, Query(gt=0, le=2_147_483_647)],
) -> None:
    await service._process_article(tenant_id, article_id)