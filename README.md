# Tenant article service

Python 3.12, FastAPI, SQLAlchemy 2 async ORM, asyncpg, PostgreSQL, Pydantic 2,
and Alembic. Function-based controllers call services, which own transactions
and delegate database access to repositories.

## Local setup

Create a dedicated PostgreSQL database named `articles` using your existing local
PostgreSQL installation, then:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Edit DATABASE_URL to match your local PostgreSQL credentials/database.
alembic upgrade head
python -m app.cli 'Example tenant'
python app/main.py
```

Set `ALLOW_DEV_TENANT_HEADER=true` for local testing as in `.env.example`. The CLI
prints the generated integer tenant ID. Use it as `X-Tenant-ID` for GET requests. Swagger documentation
is available at http://127.0.0.1:8000/docs. Database URLs must use
`postgresql+asyncpg://`; percent-encode special characters in credentials.

Existing databases at migration `0001` must also run `alembic upgrade head`.
Migration `0002` creates companies, backfills them from existing articles and their
tenant mappings, and replaces article `company_name` with a required `company_id`
foreign key. Existing articles without a tenant mapping cause the migration to
fail rather than silently assign ownership. It does not delete article data.

## Install with pip (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` contains the pinned runtime dependencies, including Celery
with Redis transport support and the Redis Python client. Redis server and Celery
worker configuration are separate from installing these packages.

## Integer ID migration

Run `alembic upgrade head` to apply revision `0004`. It converts existing
UUID IDs to generated integers and remaps company, article, and tenant foreign
keys while retaining row data. All existing public IDs and cursors change. The
conversion is forward-only; keep a pre-migration backup if UUID recovery is needed.
No migration is executed automatically by the application.

## Sample data

After applying migrations, load three tenants, four status codes, four companies,
and nine articles (three per tenant):

```bash
alembic upgrade head
psql 'postgresql://USER:PASSWORD@localhost:5432/articles' -v ON_ERROR_STOP=1 -f scripts/seed.sql
```

Use a regular PostgreSQL URL with psql, not the SQLAlchemy `postgresql+asyncpg` URL.
The seed runs in a transaction and can be rerun without overwriting existing rows.
The seed prints the generated tenant, company, and article IDs. POST accepts `tenant_id` in its JSON
payload; GET uses the `X-Tenant-ID` header for local testing.

## POST /articles

```bash
curl -X POST http://127.0.0.1:8000/articles \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":1,"company_name":"Example","title":"An article","url":"https://example.com/article","content":"Body","status":"Pending","category":null}'
```

The `ArticleCreate` Pydantic model validates this payload:

| Field | Constraint |
| --- | --- |
| tenant_id | Required positive integer referencing a tenant |
| company_name | Required, stripped, 1–255 characters |
| title | Required, stripped, 1–500 characters |
| url | Required HTTP/HTTPS URL, maximum 2048 characters, globally unique |
| content | String, defaults to empty, maximum 1,000,000 characters |
| status | Defaults to Pending; must exist in the article-status catalog |
| category | Optional nullable string, stripped, 1–128 characters |

Unexpected fields and invalid payloads return 422. URL values are normalized by
Pydantic; a duplicate stored URL returns 409. URLs are not fetched by the API.

Company names use exact, case-sensitive matching after trimming. POST atomically
creates or reuses a company for the current tenant, creates the article with its
`company_id`, and creates the tenant mapping. A unique `(tenant_id, name)`
constraint and PostgreSQL upsert handle concurrent company creation. All these
writes commit or roll back together. Companies are scoped to tenants.

The 201 response includes article `id`, `company_id`, `company_name`, title, URL,
content, status, category, and timezone-aware timestamps.

## GET /articles

```bash
curl -G http://127.0.0.1:8000/articles \
  -H 'X-Tenant-ID: REPLACE_WITH_TENANT_ID' \
  --data-urlencode 'limit=20' \
  --data-urlencode 'company_name=Example' \
  --data-urlencode 'status=Pending'
```

Optional query parameters:

| Parameter | Meaning |
| --- | --- |
| limit | Page size, default 20, range 1–100 |
| last_id | Positive integer ID of the last article from the preceding page |
| company_name | Exact company name filter, case-sensitive, trimmed |
| status | Exact article-status catalog value; invalid values return 422 |

Filters combine with AND and always include tenant scope. Response shape:

```json
{
  "items": [],
  "next_cursor": null
}
```

When there are more results, `next_cursor` contains the last returned article ID.
Pass that value as `last_id` on the next request, retaining the same filters. The
query orders by `articles.id ASC` and applies `articles.id > last_id`, fetching one
extra row to determine whether another page exists. Empty/final pages return a
null cursor. There is no offset or total-count query.

IDs are generated by PostgreSQL identity sequences (CodeMaster uses SERIAL).
Every table, including the tenant–article mapper, has an incremental integer PK.
Gaps are normal after conflicts or rollbacks. ID ordering is not a snapshot of
commit order: an earlier ID committed after pagination passed it can be missed.
Start pagination again to include such newly committed records. A cursor is a
position, not proof of access; every request independently filters by tenant.

The article API now exposes only POST and GET `/articles`; the previous
`/api/v1/articles` routes and detail/update/delete endpoints were removed.
Health endpoints remain `/health/live` and `/health/ready`.

## Structure and runtime behavior

- `app/controllers/`: HTTP endpoints and dependency wiring.
- `app/schemas/`: Pydantic payload and response models.
- `app/services/`: business validation and transaction boundaries.
- `app/repositories/`: tenant-scoped article queries and company upsert.
- `app/models/`: SQLAlchemy articles, companies, tenants, mapper, and code catalog.
- `app/db/`: async session factory and pooled engine.
- `app/core/`: settings, constants, errors, and request-context logging.
- `migrations/`: versioned PostgreSQL schema changes.

Each request gets its own AsyncSession. Repositories flush but never commit.
Closing the session rolls back unfinished work and returns its connection. Each
worker creates one pooled engine and disposes it on shutdown. Pool size, overflow,
timeouts, pre-ping and recycling are configured through settings. Budget database
connections across all workers and replicas. Do not share a session across tasks.

Statuses come from `code_master`, not an enum. Migration-managed values are Pending,
Processing, Completed, and Failed. Articles reference `code_master.id` through `status_id`. The service validates
that supplied statuses belong to the `article_status` group.

JSON access logs include request ID, path, method, status, and duration. Middleware
propagates a safe X-Request-ID or generates one, includes it in responses, and
resets the ContextVars after each request. It omits query strings and payloads.

## Production decisions still pending

The local tenant header is user-controlled. Production startup intentionally
fails until verified identity and tenant membership are implemented in
`resolve_tenant` and the settings guard is replaced. Articles currently have one
tenant owner, while URLs remain globally unique as requested: separate tenants
cannot store independent articles with the same URL. Confirm those ownership
semantics before production deployment.

Also confirm allowed status transitions, retention/audit requirements, connection
budgets, and operational controls such as gateway body limits, TLS, secret storage,
and metrics. Migrations run separately from application startup. Readiness checks
database connectivity, not migration state. There is no processing worker or queue.

## Manual verification

After migrating, create a tenant and use Swagger or curl to verify:

1. Create an article; repeat its URL and confirm 409.
2. Create two different URLs for the same company; confirm the company ID is reused.
3. Create more records than the page limit; follow `next_cursor` using `last_id`
   and confirm pages contain no repeated IDs.
4. Filter by company and status separately and together.
5. Switch tenants and confirm the first tenant's articles are absent.
6. Send invalid URLs, unknown statuses, invalid cursors, and out-of-range limits;
   confirm validation errors.

Static checks:

```bash
ruff check app migrations tests
ruff format --check app migrations tests
```

The existing automated tests have been aligned with the revised API, but were not
run for this change. To run them later, set TEST_DATABASE_URL to a migrated,
disposable PostgreSQL database whose name ends in `_test`. Integration tests
truncate tenant, company, article, and mapping tables. `requirements.txt` pins runtime dependencies.
