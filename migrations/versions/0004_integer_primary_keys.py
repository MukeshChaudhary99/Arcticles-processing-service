"""Convert UUID identifiers to generated integers, preserving row relationships.

Existing public IDs change. This migration is forward-only; restore a database
backup to recover the original UUID identifiers.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL fills existing rows using each new identity sequence.
    for table in ("tenants", "companies", "articles"):
        op.add_column(
            table, sa.Column("integer_id", sa.Integer(), sa.Identity(), nullable=False)
        )
    op.add_column(
        "companies", sa.Column("integer_tenant_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "articles", sa.Column("integer_company_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "tenant_articles", sa.Column("integer_tenant_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "tenant_articles", sa.Column("integer_article_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "tenant_articles", sa.Column("id", sa.Integer(), sa.Identity(), nullable=False)
    )

    op.execute("""
        UPDATE companies c SET integer_tenant_id = t.integer_id
        FROM tenants t WHERE t.id = c.tenant_id
    """)
    op.execute("""
        UPDATE articles a SET integer_company_id = c.integer_id
        FROM companies c WHERE c.id = a.company_id
    """)
    op.execute("""
        UPDATE tenant_articles ta SET integer_tenant_id = t.integer_id,
                                      integer_article_id = a.integer_id
        FROM tenants t, articles a
        WHERE t.id = ta.tenant_id AND a.id = ta.article_id
    """)

    for table, constraint in (
        ("companies", "fk_companies_tenant_id_tenants"),
        ("articles", "fk_articles_company_id_companies"),
        ("tenant_articles", "fk_tenant_articles_tenant_id_tenants"),
        ("tenant_articles", "fk_tenant_articles_article_id_articles"),
    ):
        op.drop_constraint(constraint, table, type_="foreignkey")

    for table in ("tenants", "companies", "articles", "tenant_articles"):
        op.drop_constraint(f"pk_{table}", table, type_="primary")

    # Dependent indexes/unique constraints on removed columns are dropped by PostgreSQL.
    for table, columns in (
        ("companies", ("tenant_id",)),
        ("articles", ("company_id",)),
        ("tenant_articles", ("tenant_id", "article_id")),
    ):
        for column in columns:
            op.drop_column(table, column)
            op.alter_column(
                table, f"integer_{column}", new_column_name=column, nullable=False
            )

    for table in ("tenants", "companies", "articles"):
        op.drop_column(table, "id")
        op.alter_column(table, "integer_id", new_column_name="id")

    for table in ("tenants", "companies", "articles", "tenant_articles"):
        op.create_primary_key(f"pk_{table}", table, ["id"])

    op.create_unique_constraint(
        "uq_companies_tenant_id", "companies", ["tenant_id", "name"]
    )
    op.create_unique_constraint(
        "uq_tenant_articles_tenant_id", "tenant_articles", ["tenant_id", "article_id"]
    )
    op.create_unique_constraint(
        "uq_tenant_articles_article_id", "tenant_articles", ["article_id"]
    )
    op.create_index("ix_articles_company_id", "articles", ["company_id"])
    for table, column, target, ondelete in (
        ("companies", "tenant_id", "tenants", "RESTRICT"),
        ("articles", "company_id", "companies", "RESTRICT"),
        ("tenant_articles", "tenant_id", "tenants", "RESTRICT"),
        ("tenant_articles", "article_id", "articles", "CASCADE"),
    ):
        op.create_foreign_key(
            f"fk_{table}_{column}_{target}",
            table,
            target,
            [column],
            ["id"],
            ondelete=ondelete,
        )

    # CodeMaster already has an integer SERIAL PK. Its initial explicit seed IDs
    # must not collide with future database-generated IDs.
    op.execute("""
        SELECT setval(pg_get_serial_sequence('code_master', 'id'),
                      COALESCE((SELECT MAX(id) FROM code_master), 1),
                      EXISTS (SELECT 1 FROM code_master))
    """)


def downgrade():
    raise RuntimeError(
        "UUID-to-integer conversion is forward-only; restore the pre-migration backup"
    )
