from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.article import ArticleRepository
from app.repositories.company import CompanyRepository
from app.services.article import ArticleService


async def resolve_tenant(
    request: Request,
    x_tenant_id: Annotated[int | None, Header(gt=0, le=2_147_483_647)] = None,
) -> int:
    # Replace this dependency with validated token + tenant membership resolution for production.
    if not request.app.state.settings.allow_dev_tenant_header:
        raise HTTPException(503, "Authenticated tenant resolver is not configured")
    if x_tenant_id is None:
        raise HTTPException(401, "X-Tenant-ID is required in development mode")
    return x_tenant_id


def get_article_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ArticleService:
    return ArticleService(ArticleRepository(session), CompanyRepository(session))
