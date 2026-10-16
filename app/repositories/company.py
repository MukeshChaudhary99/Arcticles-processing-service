from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Company


class CompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, tenant_id: int, name: str) -> int:
        # Atomic upsert also handles simultaneous article creates for the same company.
        statement = (
            insert(Company)
            .values(tenant_id=tenant_id, name=name)
            .on_conflict_do_update(
                index_elements=[Company.tenant_id, Company.name], set_={"name": name}
            )
            .returning(Company.id)
        )
        return (await self.session.execute(statement)).scalar_one()
