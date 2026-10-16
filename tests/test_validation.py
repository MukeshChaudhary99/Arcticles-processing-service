import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.schemas.article import ArticleCreate


@pytest.mark.parametrize(
    "values",
    [
        {"company_name": " ", "title": "Title", "url": "https://example.com/a"},
        {"company_name": "Company", "title": "Title", "url": "ftp://example.com/a"},
        {
            "company_name": "Company",
            "title": "Title",
            "url": "https://example.com",
            "tenant_id": "x",
        },
    ],
)
def test_invalid_create(values):
    with pytest.raises(ValidationError):
        ArticleCreate(**({"tenant_id": 1} | values))


@pytest.mark.parametrize("allow_header", [True, False])
def test_production_fails_closed(allow_header):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            environment="production",
            allow_dev_tenant_header=allow_header,
        )
