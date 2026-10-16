from datetime import datetime
from typing import ClassVar

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class CodeMaster(Base):
    __tablename__ = "code_master"
    __table_args__ = (
        UniqueConstraint("group_name", "value"),
        UniqueConstraint("id", "group_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_name: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(String(64))


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(255))


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="title_nonempty"),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    content: Mapped[str] = mapped_column(Text, default="")
    status_id: Mapped[int] = mapped_column(
        ForeignKey("code_master.id", ondelete="RESTRICT")
    )
    category: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    __mapper_args__: ClassVar[dict[str, object]] = {"version_id_col": version}


class TenantArticle(Base):
    __tablename__ = "tenant_articles"
    # Independent ownership by default; remove this constraint only after defining shared writes.
    __table_args__ = (
        UniqueConstraint("tenant_id", "article_id"),
        UniqueConstraint("article_id"),
    )
    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT")
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
