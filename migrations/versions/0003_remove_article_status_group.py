"""Replace the article status group column with a simple status foreign key."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "fk_articles_status_id_code_master", "articles", type_="foreignkey"
    )
    # Revision 0001's check name is expanded by the metadata naming convention.
    op.drop_constraint("ck_articles_status_group", "articles", type_="check")
    op.drop_column("articles", "status_group")
    op.create_foreign_key(
        "fk_articles_status_id_code_master",
        "articles",
        "code_master",
        ["status_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade():
    op.drop_constraint(
        "fk_articles_status_id_code_master", "articles", type_="foreignkey"
    )
    op.add_column("articles", sa.Column("status_group", sa.String(64), nullable=True))
    op.execute("UPDATE articles SET status_group = 'article_status'")
    op.alter_column("articles", "status_group", nullable=False)
    op.create_check_constraint(
        "ck_articles_status_group", "articles", "status_group = 'article_status'"
    )
    op.create_foreign_key(
        "fk_articles_status_id_code_master",
        "articles",
        "code_master",
        ["status_id", "status_group"],
        ["id", "group_name"],
        ondelete="RESTRICT",
    )
