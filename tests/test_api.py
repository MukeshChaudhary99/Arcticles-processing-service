import asyncio
import logging
import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, text

from app.core.logging import path_context, request_id_context
from app.core.settings import Settings
from app.main import create_app
from app.models.entities import Tenant


@pytest_asyncio.fixture
async def api():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_DATABASE_URL to a migrated disposable PostgreSQL database"
        )
    # Require explicit test DB naming to protect a normal local database.
    from sqlalchemy.engine import make_url

    if not make_url(url).database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end with _test")
    app = create_app(
        Settings(
            _env_file=None,
            database_url=url,
            environment="test",
            allow_dev_tenant_header=True,
        )
    )
    async with app.router.lifespan_context(app):
        async with app.state.database.engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE tenants, articles, tenant_articles, companies CASCADE")
            )
            first = (
                await connection.execute(
                    insert(Tenant).values(name="First").returning(Tenant.id)
                )
            ).scalar_one()
            second = (
                await connection.execute(
                    insert(Tenant).values(name="Second").returning(Tenant.id)
                )
            ).scalar_one()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, {"X-Tenant-ID": str(first)}, {"X-Tenant-ID": str(second)}, app


PAYLOAD = {
    "company_name": "Example",
    "title": "Article",
    "url": "https://example.com/a",
}
ROOT = "/articles"


async def test_create_and_tenant_isolation(api):
    client, first, second, _ = api
    response = await client.post(
        ROOT, json={**PAYLOAD, "tenant_id": int(first["X-Tenant-ID"])}
    )
    assert response.status_code == 201, response.text
    article = response.json()
    assert article["status"] == "Pending"
    assert article["company_id"]
    assert (await client.get(ROOT, headers=second)).json()["items"] == []
    assert len((await client.get(ROOT, headers=first)).json()["items"]) == 1


async def test_conflicts_and_rollback(api):
    client, first, second, _ = api
    assert (
        await client.post(
            ROOT, json={**PAYLOAD, "tenant_id": int(first["X-Tenant-ID"])}
        )
    ).status_code == 201
    assert (
        await client.post(
            ROOT, json={**PAYLOAD, "tenant_id": int(second["X-Tenant-ID"])}
        )
    ).status_code == 409
    invalid = {**PAYLOAD, "url": "https://example.com/b", "status": "Invalid"}
    assert (
        await client.post(
            ROOT, json={**invalid, "tenant_id": int(first["X-Tenant-ID"])}
        )
    ).status_code == 422
    assert len((await client.get(ROOT, headers=first)).json()["items"]) == 1
    assert (await client.get(ROOT, headers=second)).json()["items"] == []


async def test_cursor_pagination_and_filters(api):
    client, first, _, _ = api
    for i in range(3):
        payload = {**PAYLOAD, "url": f"https://example.com/{i}", "status": "Completed"}
        assert (
            await client.post(
                ROOT, json={**payload, "tenant_id": int(first["X-Tenant-ID"])}
            )
        ).status_code == 201
    params = {"limit": 2, "company_name": "Example", "status": "Completed"}
    first_page = (await client.get(ROOT, params=params, headers=first)).json()
    assert len(first_page["items"]) == 2
    assert first_page["next_cursor"] == first_page["items"][-1]["id"]
    params["last_id"] = first_page["next_cursor"]
    second_page = (await client.get(ROOT, params=params, headers=first)).json()
    assert len(second_page["items"]) == 1
    assert second_page["next_cursor"] is None
    ids = [item["id"] for item in first_page["items"] + second_page["items"]]
    assert len(set(ids)) == 3
    assert ids == sorted(ids)
    assert (
        len({item["company_id"] for item in first_page["items"] + second_page["items"]})
        == 1
    )
    assert (
        await client.get(ROOT, params={"company_name": "Other"}, headers=first)
    ).json()["items"] == []
    assert (await client.get(ROOT, params={"status": "Pending"}, headers=first)).json()[
        "items"
    ] == []


async def test_request_id_auth_and_health(api):
    client, first, _, _ = api
    assert (await client.get(ROOT)).status_code == 401
    assert (await client.get("/health/ready")).status_code == 200
    result = await client.get(ROOT, headers={**first, "X-Request-ID": "request-123"})
    assert result.headers["x-request-id"] == "request-123"
    result = await client.get(ROOT, headers={**first, "X-Request-ID": "bad id"})
    assert result.headers["x-request-id"] != "bad id"
    assert request_id_context.get() == "-"
    assert path_context.get() == "-"


async def test_context_isolation_and_unhandled_error():
    app = create_app(Settings(_env_file=None))
    logger = logging.getLogger("test.context")

    @app.get("/context/{value}")
    async def context(value: str):
        await asyncio.sleep(0)
        logger.info("context probe")
        return {"id": request_id_context.get(), "path": path_context.get()}

    @app.get("/failure")
    async def failure():
        raise RuntimeError("private error")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        results = await asyncio.gather(
            *[
                client.get(f"/context/{i}", headers={"X-Request-ID": f"req-{i}"})
                for i in range(10)
            ]
        )
        for i, result in enumerate(results):
            assert result.json() == {"id": f"req-{i}", "path": f"/context/{i}"}
        error = await client.get("/failure", headers={"X-Request-ID": "failed-request"})
        assert error.status_code == 500
        assert error.headers["x-request-id"] == "failed-request"
        assert "private error" not in error.text
        assert request_id_context.get() == "-"
