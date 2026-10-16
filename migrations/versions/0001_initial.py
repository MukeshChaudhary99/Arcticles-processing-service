"""Initial article, tenant mapping, and status catalog schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
    )
    op.create_table(
        "code_master",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_name", sa.String(64), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        sa.UniqueConstraint("group_name", "value", name="uq_code_master_group_name"),
        sa.UniqueConstraint("id", "group_name", name="uq_code_master_id"),
    )
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status_id", sa.Integer(), nullable=False),
        sa.Column("status_group", sa.String(64), nullable=False),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("url", name="uq_articles_url"),
        sa.CheckConstraint(
            "status_group = 'article_status'", name="ck_articles_status_group"
        ),
        sa.CheckConstraint(
            "length(trim(company_name)) > 0", name="ck_articles_company_name_nonempty"
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name="ck_articles_title_nonempty"
        ),
        sa.ForeignKeyConstraint(
            ["status_id", "status_group"],
            ["code_master.id", "code_master.group_name"],
            name="fk_articles_status_id_code_master",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "tenant_articles",
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.UniqueConstraint("article_id", name="uq_tenant_articles_article_id"),
    )
    catalog = sa.table(
        "code_master",
        sa.column("id", sa.Integer()),
        sa.column("group_name", sa.String()),
        sa.column("value", sa.String()),
    )
    op.bulk_insert(
        catalog,
        [
            {"id": i, "group_name": "article_status", "value": value}
            for i, value in enumerate(
                ("Pending", "Processing", "Completed", "Failed"), start=1
            )
        ],
    )


def downgrade():
    op.drop_table("tenant_articles")
    op.drop_table("articles")
    op.drop_table("code_master")
    op.drop_table("tenants")
