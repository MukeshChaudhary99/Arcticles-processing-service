"""Normalize tenant companies and preserve existing article company names."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_companies_tenant_id_tenants",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_companies_tenant_id"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_companies_name_nonempty")
        ),
    )
    op.add_column("articles", sa.Column("company_id", sa.Uuid(), nullable=True))
    # Each article currently has exactly one tenant mapping. Fail the migration if
    # legacy orphan records exist rather than silently assigning the wrong tenant.
    op.execute("""
        INSERT INTO companies (id, tenant_id, name)
        SELECT gen_random_uuid(), tenant_id, company_name
        FROM (
            SELECT DISTINCT ta.tenant_id, a.company_name
            FROM articles a JOIN tenant_articles ta ON ta.article_id = a.id
        ) AS existing_companies
    """)
    op.execute("""
        UPDATE articles a SET company_id = c.id
        FROM tenant_articles ta, companies c
        WHERE ta.article_id = a.id AND c.tenant_id = ta.tenant_id
          AND c.name = a.company_name
    """)
    op.alter_column("articles", "company_id", nullable=False)
    op.create_foreign_key(
        "fk_articles_company_id_companies",
        "articles",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_articles_company_id", "articles", ["company_id"])
    op.drop_constraint("ck_articles_company_name_nonempty", "articles", type_="check")
    op.drop_column("articles", "company_name")


def downgrade():
    op.add_column("articles", sa.Column("company_name", sa.String(255), nullable=True))
    op.execute("""
        UPDATE articles a SET company_name = c.name
        FROM companies c WHERE c.id = a.company_id
    """)
    op.alter_column("articles", "company_name", nullable=False)
    op.create_check_constraint(
        "ck_articles_company_name_nonempty",
        "articles",
        "length(trim(company_name)) > 0",
    )
    op.drop_index("ix_articles_company_id", table_name="articles")
    op.drop_constraint(
        "fk_articles_company_id_companies", "articles", type_="foreignkey"
    )
    op.drop_column("articles", "company_id")
    op.drop_table("companies")
