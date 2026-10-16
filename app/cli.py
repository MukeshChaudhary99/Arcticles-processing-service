"""Local tenant provisioning; this command is not an HTTP admin endpoint."""

import argparse
import asyncio
import json

from app.core.settings import get_settings
from app.db.session import Database
from app.models.entities import Tenant


async def create_tenant(name: str) -> None:
    database = Database(get_settings())
    try:
        async with database.sessions.begin() as session:
            tenant = Tenant(name=name)
            session.add(tenant)
            await session.flush()
            tenant_id = tenant.id
        print(json.dumps({"id": tenant_id, "name": name}))
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a local tenant")
    parser.add_argument("name")
    args = parser.parse_args()
    name = args.name.strip()
    if not name or len(name) > 200:
        parser.error("name must contain 1 to 200 characters")
    asyncio.run(create_tenant(name))


if __name__ == "__main__":
    main()
