from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

from app.core.constants import DEFAULT_ARTICLE_STATUS

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Category = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]
Status = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
Url = Annotated[HttpUrl, Field(max_length=2048)]
Content = Annotated[str, Field(max_length=1_000_000)]


class ArticleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: Annotated[int, Field(gt=0, le=2_147_483_647)]
    company_name: Name
    title: Title
    url: Url
    content: Content = ""
    category: Category | None = None
    status: Status = DEFAULT_ARTICLE_STATUS


class ArticleRead(BaseModel):
    id: int
    company_id: int
    company_name: str
    title: str
    url: str
    content: str
    status: str
    category: str | None
    created_at: datetime
    updated_at: datetime


class ArticlePage(BaseModel):
    items: list[ArticleRead]
    next_cursor: int | None = None
